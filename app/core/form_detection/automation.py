"""Automation engine for form filling."""

import asyncio
import base64
import time
from typing import Dict, List, Tuple

from playwright.async_api import async_playwright, Page, ElementHandle
import ollama

from .models import FormField
from .detector import FormDetector

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
