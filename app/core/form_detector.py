# core/form_detector.py
import asyncio
import base64
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from playwright.async_api import async_playwright, Page, ElementHandle
from PIL import Image
import requests
import ollama

@dataclass
class FormField:
    """Represents a detected form field"""
    element_id: str
    field_type: str  # text, email, file, select, textarea, etc.
    label: str
    placeholder: str
    required: bool
    coordinates: Tuple[int, int, int, int]  # x, y, width, height
    css_selector: str
    xpath: str
    confidence: float

class DetectionMethod(Enum):
    """Form detection methods"""
    DOM_ANALYSIS = "dom"
    VISUAL_DETECTION = "visual" 
    TAB_NAVIGATION = "tab"
    HYBRID = "hybrid"

class FormDetector:
    """Advanced form field detection with multiple methods"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_client = ollama.Client(host=ollama_url)
        self.page: Optional[Page] = None
        self.screenshot_cache = {}
        
    async def detect_forms(self, url: str, method: DetectionMethod = DetectionMethod.HYBRID) -> List[FormField]:
        """Detect form fields using specified method"""
        async with async_playwright() as p:
            # Launch browser with anti-detection measures
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            # Create context with fingerprint randomization
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
            )
            
            # Remove webdriver property
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            self.page = await context.new_page()
            
            try:
                await self.page.goto(url, wait_until='networkidle')
                await self.page.wait_for_timeout(2000)  # Allow dynamic content to load
                
                if method == DetectionMethod.DOM_ANALYSIS:
                    fields = await self._detect_dom_fields()
                elif method == DetectionMethod.VISUAL_DETECTION:
                    fields = await self._detect_visual_fields()
                elif method == DetectionMethod.TAB_NAVIGATION:
                    fields = await self._detect_tab_fields()
                else:  # HYBRID
                    fields = await self._detect_hybrid_fields()
                
                return fields
                
            finally:
                await browser.close()

    async def _detect_dom_fields(self) -> List[FormField]:
        """Detect form fields using DOM analysis"""
        fields = []
        
        # Enhanced selectors for various input types
        selectors = [
            'input[type="text"]',
            'input[type="email"]', 
            'input[type="tel"]',
            'input[type="password"]',
            'input[type="file"]',
            'input[type="number"]',
            'input[type="date"]',
            'input[type="url"]',
            'input:not([type])',  # Default text inputs
            'textarea',
            'select',
            '[contenteditable="true"]',  # Rich text editors
            '[role="textbox"]',  # ARIA textboxes
            '.file-upload',  # Common CSS classes
            '.file-drop-zone',
            '[data-testid*="upload"]',  # Test IDs
            '[aria-label*="upload"]'  # Accessibility labels
        ]
        
        for selector in selectors:
            elements = await self.page.query_selector_all(selector)
            
            for element in elements:
                try:
                    field = await self._analyze_element(element, selector)
                    if field and await self._is_visible(element):
                        fields.append(field)
                except Exception as e:
                    print(f"Error analyzing element {selector}: {e}")
                    continue
        
        return fields

    async def _detect_visual_fields(self) -> List[FormField]:
        """Detect form fields using computer vision"""
        # Take screenshot
        screenshot = await self.page.screenshot(full_page=True)
        
        # Convert to numpy array for OpenCV
        nparr = np.frombuffer(screenshot, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Use LLaVA for visual form understanding
        base64_img = base64.b64encode(screenshot).decode('utf-8')
        
        prompt = """
        Analyze this webpage screenshot and identify all form fields including:
        1. Text input fields
        2. Email input fields  
        3. File upload buttons/areas
        4. Dropdown selects
        5. Textareas
        6. Any interactive form elements
        
        For each field, provide:
        - Type of field
        - Approximate coordinates (x, y, width, height)
        - Associated label text
        - Whether it appears required
        
        Return as JSON array.
        """
        
        try:
            response = self.ollama_client.generate(
                model='llava:7b',
                prompt=prompt,
                images=[base64_img]
            )
            
            # Parse LLaVA response and convert to FormField objects
            visual_fields = await self._parse_visual_response(response['response'])
            return visual_fields
            
        except Exception as e:
            print(f"Visual detection error: {e}")
            return []

    async def _detect_tab_fields(self) -> List[FormField]:
        """Detect form fields using tab navigation"""
        fields = []
        visited_elements = set()
        
        # Start from beginning of page
        await self.page.keyboard.press('Home')
        await self.page.wait_for_timeout(500)
        
        # Tab through all focusable elements
        for i in range(100):  # Limit to prevent infinite loops
            await self.page.keyboard.press('Tab')
            await self.page.wait_for_timeout(100)
            
            # Get currently focused element
            focused = await self.page.evaluate("""
                () => {
                    const element = document.activeElement;
                    if (!element) return null;
                    
                    return {
                        tagName: element.tagName,
                        type: element.type || '',
                        id: element.id || '',
                        name: element.name || '',
                        className: element.className || '',
                        placeholder: element.placeholder || '',
                        required: element.required || false,
                        offsetLeft: element.offsetLeft,
                        offsetTop: element.offsetTop,
                        offsetWidth: element.offsetWidth,
                        offsetHeight: element.offsetHeight
                    };
                }
            """)
            
            if not focused:
                continue
                
            # Create unique identifier
            element_key = f"{focused['tagName']}_{focused.get('id', '')}_{focused.get('name', '')}_{focused['offsetLeft']}_{focused['offsetTop']}"
            
            if element_key in visited_elements:
                break  # We've cycled through all tabbable elements
                
            visited_elements.add(element_key)
            
            # Check if it's a form field
            if self._is_form_element(focused):
                field = await self._create_field_from_focused(focused)
                if field:
                    fields.append(field)
        
        return fields

    async def _detect_hybrid_fields(self) -> List[FormField]:
        """Combine multiple detection methods for maximum accuracy"""
        dom_fields = await self._detect_dom_fields()
        visual_fields = await self._detect_visual_fields()
        tab_fields = await self._detect_tab_fields()
        
        # Merge and deduplicate fields
        all_fields = {}
        
        # Add DOM fields (highest confidence)
        for field in dom_fields:
            key = self._get_field_key(field)
            all_fields[key] = field
            all_fields[key].confidence = min(field.confidence + 0.3, 1.0)
        
        # Add visual fields (medium confidence)
        for field in visual_fields:
            key = self._get_field_key(field)
            if key not in all_fields:
                all_fields[key] = field
            else:
                # Merge information
                all_fields[key].confidence = min(all_fields[key].confidence + 0.2, 1.0)
        
        # Add tab fields (lower confidence but catches missed elements)
        for field in tab_fields:
            key = self._get_field_key(field)
            if key not in all_fields:
                all_fields[key] = field
        
        return list(all_fields.values())

    async def _analyze_element(self, element: ElementHandle, selector: str) -> Optional[FormField]:
        """Analyze a DOM element to create FormField"""
        try:
            # Get element properties
            props = await element.evaluate("""
                (el) => {
                    const rect = el.getBoundingClientRect();
                    const label = el.labels?.[0]?.textContent || 
                                 el.getAttribute('aria-label') ||
                                 el.getAttribute('placeholder') ||
                                 el.getAttribute('title') ||
                                 el.parentElement?.querySelector('label')?.textContent ||
                                 '';
                    
                    return {
                        id: el.id || '',
                        name: el.name || '',
                        type: el.type || el.tagName.toLowerCase(),
                        placeholder: el.placeholder || '',
                        required: el.required || false,
                        value: el.value || '',
                        className: el.className || '',
                        tagName: el.tagName,
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height,
                        label: label.trim()
                    };
                }
            """)
            
            # Generate selectors
            css_selector = await self._generate_css_selector(element)
            xpath = await self._generate_xpath(element)
            
            # Determine field type with AI assistance
            field_type = await self._classify_field_type(props, selector)
            
            return FormField(
                element_id=props['id'] or f"element_{hash(css_selector)}",
                field_type=field_type,
                label=props['label'],
                placeholder=props['placeholder'],
                required=props['required'],
                coordinates=(props['x'], props['y'], props['width'], props['height']),
                css_selector=css_selector,
                xpath=xpath,
                confidence=0.8
            )
            
        except Exception as e:
            print(f"Error analyzing element: {e}")
            return None

    async def _classify_field_type(self, props: Dict, selector: str) -> str:
        """Classify field type using AI and heuristics"""
        # Basic type mapping
        type_mapping = {
            'email': 'email',
            'tel': 'phone',
            'file': 'file_upload',
            'password': 'password',
            'number': 'number',
            'date': 'date',
            'url': 'url',
            'textarea': 'textarea',
            'select': 'select'
        }
        
        if props['type'] in type_mapping:
            return type_mapping[props['type']]
        
        # AI-powered classification for ambiguous cases
        context = f"""
        Field properties:
        - Tag: {props['tagName']}
        - Type: {props['type']}
        - Label: {props['label']}
        - Placeholder: {props['placeholder']}
        - CSS Classes: {props['className']}
        - Selector: {selector}
        
        Classify this form field type. Options: text, email, phone, file_upload, 
        name, address, company, position, salary, skills, experience, education
        """
        
        try:
            response = self.ollama_client.generate(
                model='mistral:7b-instruct',
                prompt=context,
                options={'temperature': 0.1}
            )
            
            classified_type = response['response'].strip().lower()
            return classified_type if classified_type else 'text'
            
        except:
            return 'text'  # Default fallback

    async def _generate_css_selector(self, element: ElementHandle) -> str:
        """Generate robust CSS selector"""
        return await element.evaluate("""
            (el) => {
                if (el.id) return '#' + el.id;
                
                let selector = el.tagName.toLowerCase();
                if (el.className) {
                    selector += '.' + el.className.split(' ').join('.');
                }
                
                // Add attribute selectors for uniqueness
                if (el.name) selector += `[name="${el.name}"]`;
                if (el.type && el.type !== 'text') selector += `[type="${el.type}"]`;
                if (el.placeholder) selector += `[placeholder*="${el.placeholder.substring(0, 10)}"]`;
                
                return selector;
            }
        """)

    async def _generate_xpath(self, element: ElementHandle) -> str:
        """Generate XPath selector"""
        return await element.evaluate("""
            (el) => {
                if (el.id) return `//*[@id="${el.id}"]`;
                
                let path = '';
                let current = el;
                
                while (current && current.nodeType === Node.ELEMENT_NODE) {
                    let selector = current.nodeName.toLowerCase();
                    if (current.id) {
                        selector += `[@id="${current.id}"]`;
                        path = `//${selector}${path}`;
                        break;
                    }
                    
                    let sibling = current;
                    let nth = 1;
                    while (sibling = sibling.previousElementSibling) {
                        if (sibling.nodeName.toLowerCase() === selector.split('[')[0]) nth++;
                    }
                    
                    if (nth > 1) selector += `[${nth}]`;
                    path = `/${selector}${path}`;
                    current = current.parentElement;
                }
                
                return path;
            }
        """)

    async def _is_visible(self, element: ElementHandle) -> bool:
        """Check if element is visible"""
        return await element.evaluate("""
            (el) => {
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       style.opacity !== '0' &&
                       el.offsetWidth > 0 && 
                       el.offsetHeight > 0;
            }
        """)

    def _is_form_element(self, element_info: Dict) -> bool:
        """Check if focused element is a form field"""
        form_tags = {'INPUT', 'TEXTAREA', 'SELECT'}
        form_types = {'text', 'email', 'tel', 'password', 'file', 'number', 'date', 'url'}
        
        if element_info['tagName'] in form_tags:
            if element_info['tagName'] == 'INPUT':
                return element_info.get('type', 'text') in form_types
            return True
        
        return False

    async def _create_field_from_focused(self, focused: Dict) -> Optional[FormField]:
        """Create FormField from focused element info"""
        try:
            field_type = focused.get('type', 'text')
            if focused['tagName'] == 'TEXTAREA':
                field_type = 'textarea'
            elif focused['tagName'] == 'SELECT':
                field_type = 'select'
            
            # Generate basic selectors
            css_selector = f"{focused['tagName'].lower()}"
            if focused.get('id'):
                css_selector = f"#{focused['id']}"
            elif focused.get('name'):
                css_selector += f"[name='{focused['name']}']"
            
            return FormField(
                element_id=focused.get('id', f"tab_element_{hash(str(focused))}"),
                field_type=field_type,
                label=focused.get('placeholder', ''),
                placeholder=focused.get('placeholder', ''),
                required=focused.get('required', False),
                coordinates=(
                    focused['offsetLeft'],
                    focused['offsetTop'], 
                    focused['offsetWidth'],
                    focused['offsetHeight']
                ),
                css_selector=css_selector,
                xpath=f"//{focused['tagName'].lower()}",
                confidence=0.6
            )
        except:
            return None

    async def _parse_visual_response(self, response: str) -> List[FormField]:
        """Parse LLaVA response into FormField objects"""
        fields = []
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                for item in data:
                    if isinstance(item, dict):
                        field = FormField(
                            element_id=f"visual_{hash(str(item))}",
                            field_type=item.get('type', 'text'),
                            label=item.get('label', ''),
                            placeholder=item.get('placeholder', ''),
                            required=item.get('required', False),
                            coordinates=(
                                item.get('x', 0),
                                item.get('y', 0),
                                item.get('width', 0),
                                item.get('height', 0)
                            ),
                            css_selector='',  # Visual detection doesn't provide selectors
                            xpath='',
                            confidence=0.7
                        )
                        fields.append(field)
        except:
            pass  # Visual detection failed, return empty list
        
        return fields

    def _get_field_key(self, field: FormField) -> str:
        """Generate unique key for field deduplication"""
        return f"{field.field_type}_{field.coordinates[0]}_{field.coordinates[1]}"


# core/automation_engine.py
class AutomationEngine:
    """Advanced form filling automation engine"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_client = ollama.Client(host=ollama_url)
        self.form_detector = FormDetector(ollama_url)
        
    async def fill_forms(self, cv_data: Dict, url: str = None) -> Dict:
        """Fill forms automatically using CV data"""
        results = {
            'success': False,
            'fields_filled': 0,
            'errors': [],
            'screenshots': []
        }
        
        async with async_playwright() as p:
            browser = await self._launch_stealth_browser(p)
            context = await self._create_stealth_context(browser)
            page = await context.new_page()
            
            try:
                if url:
                    await page.goto(url, wait_until='networkidle')
                
                # Detect forms
                fields = await self.form_detector.detect_forms(page.url)
                
                if not fields:
                    results['errors'].append("No form fields detected")
                    return results
                
                # Fill each field
                for field in fields:
                    try:
                        filled = await self._fill_field(page, field, cv_data)
                        if filled:
                            results['fields_filled'] += 1
                    except Exception as e:
                        results['errors'].append(f"Error filling {field.element_id}: {str(e)}")
                
                # Handle file uploads separately
                await self._handle_file_uploads(page, fields, cv_data)
                
                # Take screenshot for verification
                screenshot = await page.screenshot(full_page=True)
                results['screenshots'].append(base64.b64encode(screenshot).decode())
                
                results['success'] = results['fields_filled'] > 0
                
            finally:
                await browser.close()
        
        return results

    async def _launch_stealth_browser(self, playwright):
        """Launch browser with advanced anti-detection"""
        return await playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-field-trial-config',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--disable-sync',
                '--force-color-profile=srgb',
                '--metrics-recording-only',
                '--safebrowsing-disable-auto-update',
                '--enable-automation',
                '--password-store=basic',
                '--use-mock-keychain'
            ]
        )

    async def _create_stealth_context(self, browser):
        """Create browser context with fingerprint randomization"""
        # Randomize viewport
        viewports = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1440, 'height': 900},
            {'width': 1536, 'height': 864}
        ]
        viewport = viewports[int(time.time()) % len(viewports)]
        
        # Randomize user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ]
        user_agent = user_agents[int(time.time()) % len(user_agents)]
        
        context = await browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        
        # Inject stealth scripts
        await context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)
        
        return context

    async def _fill_field(self, page: Page, field: FormField, cv_data: Dict) -> bool:
        """Fill individual form field"""
        try:
            # Get field value from CV data
            value = self._get_field_value(field, cv_data)
            if not value:
                return False
            
            # Try multiple selector strategies
            element = None
            selectors = [field.css_selector, field.xpath, f"#{field.element_id}"]
            
            for selector in selectors:
                if not selector:
                    continue
                try:
                    if selector.startswith('/'):  # XPath
                        element = await page.wait_for_selector(f"xpath={selector}", timeout=2000)
                    else:  # CSS
                        element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        break
                except:
                    continue
            
            if not element:
                return False
            
            # Handle different field types
            if field.field_type == 'file_upload':
                return await self._handle_file_upload(page, element, cv_data)
            elif field.field_type in ['select', 'dropdown']:
                return await self._handle_select(page, element, value)
            elif field.field_type == 'textarea':
                return await self._handle_textarea(page, element, value)
            else:
                return await self._handle_text_input(page, element, value)
                
        except Exception as e:
            print(f"Error filling field {field.element_id}: {e}")
            return False

    def _get_field_value(self, field: FormField, cv_data: Dict) -> str:
        """Extract appropriate value from CV data for field"""
        field_mapping = {
            'name': cv_data.get('name', ''),
            'email': cv_data.get('email', ''),
            'phone': cv_data.get('phone', ''),
            'address': cv_data.get('location', ''),
            'position': cv_data.get('title', ''),
            'company': cv_data.get('current_company', ''),
            'experience': str(cv_data.get('experience_years', '')),
            'skills': ', '.join(cv_data.get('skills', [])),
            'salary': cv_data.get('expected_salary', ''),
            'education': cv_data.get('education', '')
        }
        
        # Use AI to match field to appropriate data
        if field.field_type in field_mapping:
            return field_mapping[field.field_type]
        
        # Intelligent matching using field labels
        label_keywords = {
            'first': cv_data.get('name', '').split()[0] if cv_data.get('name') else '',
            'last': cv_data.get('name', '').split()[-1] if cv_data.get('name') else '',
            'email': cv_data.get('email', ''),
            'phone': cv_data.get('phone', ''),
            'mobile': cv_data.get('phone', ''),
            'city': cv_data.get('location', ''),
            'country': 'Poland',  # Default
            'linkedin': cv_data.get('linkedin', ''),
            'website': cv_data.get('website', ''),
            'portfolio': cv_data.get('portfolio', '')
        }
        
        for keyword, value in label_keywords.items():
            if keyword.lower() in field.label.lower() or keyword.lower() in field.placeholder.lower():
                return value
        
        return ''

    async def _handle_file_upload(self, page: Page, element, cv_data: Dict) -> bool:
        """Handle file upload fields"""
        try:
            # Assuming CV file is stored temporarily
            cv_file_path = cv_data.get('file_path')
            if not cv_file_path:
                return False
            
            # Set input files
            await element.set_input_files(cv_file_path)
            await page.wait_for_timeout(1000)  # Wait for upload
            
            return True
        except:
            return False

    async def _handle_select(self, page: Page, element, value: str) -> bool:
        """Handle select dropdown fields"""
        try:
            # Try to select by value, then by text
            try:
                await element.select_option(value=value)
            except:
                await element.select_option(label=value)
            return True
        except:
            return False

    async def _handle_textarea(self, page: Page, element, value: str) -> bool:
        """Handle textarea fields"""
        try:
            await element.click()
            await element.fill(value)
            return True
        except:
            return False

    async def _handle_text_input(self, page: Page, element, value: str) -> bool:
        """Handle text input fields with human-like typing"""
        try:
            await element.click()
            await element.fill('')  # Clear existing content
            
            # Human-like typing with random delays
            for char in value:
                await element.type(char)
                await page.wait_for_timeout(50 + int(time.time() * 1000) % 100)
            
            return True
        except:
            return False

    async def _handle_file_uploads(self, page: Page, fields: List[FormField], cv_data: Dict):
        """Handle multiple file upload strategies"""
        file_fields = [f for f in fields if f.field_type == 'file_upload']
        
        for field in file_fields:
            # Try drag and drop upload
            try:
                await self._try_drag_drop_upload(page, field, cv_data)
            except:
                pass
            
            # Try click upload
            try:
                await self._try_click_upload(page, field, cv_data)
            except:
                pass

    async def _try_drag_drop_upload(self, page: Page, field: FormField, cv_data: Dict):
        """Try drag and drop file upload"""
        cv_file_path = cv_data.get('file_path')
        if not cv_file_path:
            return
        
        # Simulate drag and drop
        file_input = await page.query_selector(field.css_selector)
        if file_input:
            await file_input.set_input_files(cv_file_path)

    async def _try_click_upload(self, page: Page, field: FormField, cv_data: Dict):
        """Try click-based file upload"""
        cv_file_path = cv_data.get('file_path')
        if not cv_file_path:
            return
        
        # Look for upload buttons near the field
        upload_buttons = await page.query_selector_all("""
            button:has-text("upload"), 
            button:has-text("choose"), 
            button:has-text("browse"),
            input[type="file"],
            .upload-btn,
            .file-upload-btn
        """)
        
        for button in upload_buttons:
            try:
                # Check if button is near the field
                button_box = await button.bounding_box()
                field_box = field.coordinates
                
                if button_box and self._is_near(button_box, field_box):
                    if await button.get_attribute('type') == 'file':
                        await button.set_input_files(cv_file_path)
                    else:
                        await button.click()
                        # Handle file dialog
                        async with page.expect_file_chooser() as fc_info:
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(cv_file_path)
                    break
            except:
                continue

    def _is_near(self, box1: Dict, box2: Tuple) -> bool:
        """Check if two elements are near each other"""
        distance_threshold = 200  # pixels
        
        x1, y1 = box1['x'] + box1['width']/2, box1['y'] + box1['height']/2
        x2, y2 = box2[0] + box2[2]/2, box2[1] + box2[3]/2
        
        distance = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
        return distance < distance_threshold