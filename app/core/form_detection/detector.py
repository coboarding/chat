"""Form detector module for detecting form fields on web pages."""

import asyncio
import base64
import json
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from playwright.async_api import async_playwright, Page, ElementHandle
import ollama

from .models import FormField, DetectionMethod

class FormDetector:
    """Advanced form field detection with multiple methods"""
    
    # Class variables for singleton pattern
    _instance = None
    _initialized = False
    _browser = None
    _context = None
    _page = None
    _playwright = None
    
    def __new__(cls, *args, **kwargs):
        # Singleton pattern to ensure only one instance exists
        if cls._instance is None:
            cls._instance = super(FormDetector, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        # Only initialize once
        if not FormDetector._initialized:
            self.ollama_client = ollama.Client(host=ollama_url)
            self.screenshot_cache = {}
            FormDetector._initialized = True
        
    @classmethod
    async def initialize_browser(cls):
        """Initialize browser if not already initialized"""
        if cls._browser is None:
            try:
                # Start playwright
                cls._playwright = await async_playwright().start()
                
                # Launch browser with anti-detection measures
                cls._browser = await cls._playwright.chromium.launch(
                    headless=True,
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
                cls._context = await cls._browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                    }
                )
                
                # Remove webdriver property
                await cls._context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                """)
                
                cls._page = await cls._context.new_page()
                print("Browser initialized successfully")
            except Exception as e:
                print(f"Error initializing browser: {e}")
                # Clean up resources if initialization fails
                await cls.close_browser()
    
    @classmethod
    async def close_browser(cls):
        """Close browser and clean up resources"""
        try:
            if cls._browser:
                await cls._browser.close()
                cls._browser = None
                
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
                
            cls._context = None
            cls._page = None
            print("Browser closed successfully")
        except Exception as e:
            print(f"Error closing browser: {e}")
    
    async def detect_forms(self, url: str, method: DetectionMethod = DetectionMethod.HYBRID) -> List[FormField]:
        """Detect form fields using specified method"""
        try:
            # Initialize browser if needed
            await self.__class__.initialize_browser()
            
            # Navigate to URL
            await self.__class__._page.goto(url, wait_until='networkidle')
            await self.__class__._page.wait_for_timeout(2000)  # Allow dynamic content to load
            
            # Detect fields using specified method
            if method == DetectionMethod.DOM_ANALYSIS:
                fields = await self._detect_dom_fields()
            elif method == DetectionMethod.VISUAL_DETECTION:
                fields = await self._detect_visual_fields()
            elif method == DetectionMethod.TAB_NAVIGATION:
                fields = await self._detect_tab_fields()
            else:  # HYBRID
                fields = await self._detect_hybrid_fields()
            
            return fields
        except Exception as e:
            print(f"Error detecting forms: {e}")
            # Don't close the browser on error, just return empty list
            return []

    async def _detect_dom_fields(self) -> List[FormField]:
        """Detect form fields using DOM analysis"""
        if not self.__class__._page:
            print("Browser page not initialized")
            return []
            
        fields = []
        
        # Enhanced selectors for various input types
        selectors = [
            'input[type="text"]',
            'input[type="email"]',
            'input[type="password"]',
            'input[type="tel"]',
            'input[type="number"]',
            'input[type="file"]',
            'input[type="date"]',
            'select',
            'textarea',
            'div[role="textbox"]',
            'div[contenteditable="true"]',
            '.form-control',
            '[aria-required="true"]'
        ]
        
        # Find all form fields
        for selector in selectors:
            elements = await self.__class__._page.query_selector_all(selector)
            
            for element in elements:
                try:
                    # Get element properties
                    properties = await element.evaluate("""
                        (el) => {
                            const rect = el.getBoundingClientRect();
                            const computedStyle = window.getComputedStyle(el);
                            
                            // Find associated label
                            let label = '';
                            
                            // Check for label element
                            if (el.id) {
                                const labelElement = document.querySelector(`label[for="${el.id}"]`);
                                if (labelElement) {
                                    label = labelElement.textContent.trim();
                                }
                            }
                            
                            // Check for aria-label
                            if (!label && el.getAttribute('aria-label')) {
                                label = el.getAttribute('aria-label');
                            }
                            
                            // Check for placeholder as fallback
                            if (!label && el.getAttribute('placeholder')) {
                                label = el.getAttribute('placeholder');
                            }
                            
                            // Check for parent label
                            if (!label) {
                                let parent = el.parentElement;
                                while (parent && parent.tagName !== 'FORM' && parent.tagName !== 'BODY') {
                                    if (parent.tagName === 'LABEL') {
                                        label = parent.textContent.trim();
                                        break;
                                    }
                                    parent = parent.parentElement;
                                }
                            }
                            
                            // Check for nearby text nodes
                            if (!label) {
                                const walker = document.createTreeWalker(
                                    document.body, 
                                    NodeFilter.SHOW_TEXT, 
                                    null, 
                                    false
                                );
                                
                                let node;
                                let closestNode = null;
                                let closestDistance = Infinity;
                                
                                while (node = walker.nextNode()) {
                                    const text = node.textContent.trim();
                                    if (text) {
                                        const nodeRect = node.parentElement.getBoundingClientRect();
                                        const distance = Math.sqrt(
                                            Math.pow(rect.left - nodeRect.left, 2) + 
                                            Math.pow(rect.top - nodeRect.top, 2)
                                        );
                                        
                                        if (distance < 100 && distance < closestDistance) {
                                            closestDistance = distance;
                                            closestNode = node;
                                        }
                                    }
                                }
                                
                                if (closestNode) {
                                    label = closestNode.textContent.trim();
                                }
                            }
                            
                            return {
                                id: el.id || '',
                                type: el.type || el.tagName.toLowerCase(),
                                name: el.name || '',
                                placeholder: el.placeholder || '',
                                value: el.value || '',
                                required: el.required || el.getAttribute('aria-required') === 'true',
                                disabled: el.disabled || computedStyle.display === 'none',
                                label: label,
                                rect: {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height
                                },
                                cssSelector: getCssPath(el),
                                xpath: getXPath(el)
                            };
                            
                            function getCssPath(el) {
                                if (!(el instanceof Element)) return;
                                const path = [];
                                while (el.nodeType === Node.ELEMENT_NODE) {
                                    let selector = el.nodeName.toLowerCase();
                                    if (el.id) {
                                        selector += '#' + el.id;
                                        path.unshift(selector);
                                        break;
                                    } else {
                                        let sibling = el;
                                        let nth = 1;
                                        while (sibling = sibling.previousElementSibling) {
                                            if (sibling.nodeName.toLowerCase() === selector) nth++;
                                        }
                                        if (nth !== 1) selector += ":nth-of-type("+nth+")";
                                    }
                                    path.unshift(selector);
                                    el = el.parentNode;
                                }
                                return path.join(' > ');
                            }
                            
                            function getXPath(el) {
                                if (el.id) return `//*[@id="${el.id}"]`;
                                
                                const parts = [];
                                while (el && el.nodeType === Node.ELEMENT_NODE) {
                                    let idx = 0;
                                    let sibling = el;
                                    while (sibling) {
                                        if (sibling.nodeName === el.nodeName) idx++;
                                        sibling = sibling.previousElementSibling;
                                    }
                                    const tagName = el.nodeName.toLowerCase();
                                    const pathIndex = idx ? `[${idx}]` : '';
                                    parts.unshift(`${tagName}${pathIndex}`);
                                    el = el.parentNode;
                                }
                                return `/${parts.join('/')}`;
                            }
                        }
                    """)
                    
                    # Create FormField object
                    field = FormField(
                        element_id=properties.get('id', ''),
                        field_type=properties.get('type', 'unknown'),
                        label=properties.get('label', ''),
                        placeholder=properties.get('placeholder', ''),
                        required=properties.get('required', False),
                        coordinates=(
                            properties.get('rect', {}).get('x', 0),
                            properties.get('rect', {}).get('y', 0),
                            properties.get('rect', {}).get('width', 0),
                            properties.get('rect', {}).get('height', 0)
                        ),
                        css_selector=properties.get('cssSelector', ''),
                        xpath=properties.get('xpath', ''),
                        confidence=0.9  # High confidence for DOM detection
                    )
                    
                    fields.append(field)
                except Exception as e:
                    print(f"Error processing element: {e}")
        
        return fields

    async def _detect_visual_fields(self) -> List[FormField]:
        """Detect form fields using visual detection"""
        if not self.__class__._page:
            print("Browser page not initialized")
            return []
            
        fields = []
        
        try:
            # Take screenshot
            screenshot = await self.__class__._page.screenshot(type='jpeg', quality=80)
            
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
        
        except Exception as e:
            print(f"Error in visual fields detection: {e}")
            return []

    async def _detect_tab_fields(self) -> List[FormField]:
        """Detect form fields using tab navigation"""
        if not self.__class__._page:
            print("Browser page not initialized")
            return []
            
        fields = []
        visited_elements = set()
        
        try:
            # Start from the beginning of the page
            await self.__class__._page.keyboard.press('Home')
            await self.__class__._page.wait_for_timeout(500)
            
            # Tab through all focusable elements
            for i in range(100):  # Limit to prevent infinite loops
                await self.__class__._page.keyboard.press('Tab')
                await self.__class__._page.wait_for_timeout(100)
                
                # Get currently focused element
                focused = await self.__class__._page.evaluate("""
                    () => {
                        const element = document.activeElement;
                        if (!element) return null;
                        
                        const rect = element.getBoundingClientRect();
                        const isInput = element.tagName === 'INPUT' || 
                                        element.tagName === 'SELECT' || 
                                        element.tagName === 'TEXTAREA' ||
                                        element.getAttribute('contenteditable') === 'true';
                        
                        if (!isInput) return null;
                        
                        // Find label
                        let label = '';
                        if (element.id) {
                            const labelEl = document.querySelector(`label[for="${element.id}"]`);
                            if (labelEl) label = labelEl.textContent.trim();
                        }
                        
                        if (!label && element.placeholder) {
                            label = element.placeholder;
                        }
                        
                        return {
                            id: element.id || '',
                            type: element.type || element.tagName.toLowerCase(),
                            label: label,
                            placeholder: element.placeholder || '',
                            required: element.required || false,
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            outerHTML: element.outerHTML
                        };
                    }
                """)
                
                if not focused or not focused.get('id'):
                    continue
                    
                # Skip if already processed
                element_id = focused.get('id')
                if element_id in visited_elements:
                    continue
                    
                visited_elements.add(element_id)
                
                # Create FormField
                field = FormField(
                    element_id=element_id,
                    field_type=focused.get('type', 'unknown'),
                    label=focused.get('label', ''),
                    placeholder=focused.get('placeholder', ''),
                    required=focused.get('required', False),
                    coordinates=(
                        focused.get('x', 0),
                        focused.get('y', 0),
                        focused.get('width', 0),
                        focused.get('height', 0)
                    ),
                    css_selector='',  # Not available through this method
                    xpath='',         # Not available through this method
                    confidence=0.7    # Medium confidence for tab navigation
                )
                
                fields.append(field)
                
        except Exception as e:
            print(f"Tab navigation error: {e}")
            
        return fields

    async def _detect_hybrid_fields(self) -> List[FormField]:
        """Detect form fields using multiple methods"""
        if not self.__class__._page:
            print("Browser page not initialized")
            return []
            
        # Run all detection methods and combine results
        dom_fields = await self._detect_dom_fields()
        visual_fields = await self._detect_visual_fields()
        tab_fields = await self._detect_tab_fields()
        
        # Combine results with deduplication
        all_fields = {}
        
        # Add DOM fields (highest priority)
        for field in dom_fields:
            key = f"{field.element_id}_{field.field_type}_{field.coordinates}"
            all_fields[key] = field
            
        # Add tab fields if not already present
        for field in tab_fields:
            key = f"{field.element_id}_{field.field_type}_{field.coordinates}"
            if key not in all_fields:
                all_fields[key] = field
            else:
                # Merge label information if available
                if field.label and not all_fields[key].label:
                    all_fields[key].label = field.label
                    
        # Add visual fields if not already present
        for field in visual_fields:
            # Find closest match based on coordinates
            closest_match = None
            min_distance = float('inf')
            
            for key, existing_field in all_fields.items():
                x1, y1, w1, h1 = existing_field.coordinates
                x2, y2, w2, h2 = field.coordinates
                
                # Calculate center points
                cx1, cy1 = x1 + w1/2, y1 + h1/2
                cx2, cy2 = x2 + w2/2, y2 + h2/2
                
                # Calculate distance between centers
                distance = ((cx1 - cx2)**2 + (cy1 - cy2)**2)**0.5
                
                if distance < min_distance and distance < 50:  # 50px threshold
                    min_distance = distance
                    closest_match = key
            
            if closest_match:
                # Merge label information if available
                if field.label and not all_fields[closest_match].label:
                    all_fields[closest_match].label = field.label
            else:
                # Add as new field
                key = f"visual_{field.field_type}_{field.coordinates}"
                all_fields[key] = field
                
        return list(all_fields.values())

    async def _parse_visual_response(self, text: str) -> List[FormField]:
        """Parse visual LLM response into FormField objects"""
        fields = []
        
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if not json_match:
                print("No JSON found in visual response")
                return fields
                
            json_str = json_match.group(0)
            form_data = json.loads(json_str)
            
            # Convert to FormField objects
            for item in form_data:
                try:
                    field = FormField(
                        element_id=f"visual_{len(fields)}",
                        field_type=item.get('type', 'unknown').lower(),
                        label=item.get('label', ''),
                        placeholder='',
                        required=item.get('required', False),
                        coordinates=(
                            item.get('x', 0),
                            item.get('y', 0),
                            item.get('width', 100),
                            item.get('height', 30)
                        ),
                        css_selector='',
                        xpath='',
                        confidence=0.6  # Lower confidence for visual detection
                    )
                    fields.append(field)
                except Exception as e:
                    print(f"Error parsing field: {e}")
            
        except Exception as e:
            print(f"Error parsing visual response: {e}")
            
        return fields
