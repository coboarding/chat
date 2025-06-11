# worker/core/automation_worker.py
"""
Core automation worker for form detection, filling, and job applications
Handles browser automation using Playwright with anti-detection measures
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import random
import string

from playwright.async_api import async_playwright, Page, BrowserContext
import aioredis
from loguru import logger
import cv2
import numpy as np
from PIL import Image
import base64

from utils.helpers import WorkerConfig, TaskValidationError, BrowserAutomationError


class AutomationWorker:
    """Core automation worker for browser-based tasks"""

    def __init__(self, redis_client: aioredis.Redis, config: WorkerConfig):
        self.redis = redis_client
        self.config = config
        self.active_tasks = 0
        self.browser_contexts = {}

        # Anti-detection settings
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ]

        self.viewports = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1440, 'height': 900},
            {'width': 1536, 'height': 864}
        ]

    async def detect_forms(self, url: str, method: str = 'hybrid') -> Dict[str, Any]:
        """Detect forms on a webpage using specified method"""
        start_time = time.time()
        self.active_tasks += 1

        try:
            logger.info(f"Starting form detection on {url} using {method} method")

            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await self._create_context(browser)
                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(2000)  # Allow dynamic content to load

                    # Detect forms based on method
                    if method == 'dom':
                        fields = await self._detect_forms_dom(page)
                    elif method == 'visual':
                        fields = await self._detect_forms_visual(page)
                    elif method == 'tab':
                        fields = await self._detect_forms_tab(page)
                    else:  # hybrid
                        fields = await self._detect_forms_hybrid(page)

                    processing_time = time.time() - start_time

                    logger.info(f"Form detection completed: {len(fields)} fields found in {processing_time:.2f}s")

                    return {
                        'success': True,
                        'url': url,
                        'method': method,
                        'fields': [self._serialize_field(field) for field in fields],
                        'processing_time': processing_time,
                        'timestamp': datetime.utcnow().isoformat()
                    }

                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Form detection failed: {e}")

            return {
                'success': False,
                'url': url,
                'method': method,
                'error': str(e),
                'processing_time': processing_time,
                'timestamp': datetime.utcnow().isoformat()
            }
        finally:
            self.active_tasks -= 1

    async def fill_forms(self, url: str, cv_data: Dict, form_fields: List[Dict] = None) -> Dict[str, Any]:
        """Fill forms on a webpage using CV data"""
        start_time = time.time()
        self.active_tasks += 1

        try:
            logger.info(f"Starting form filling on {url}")

            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await self._create_context(browser)
                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(2000)

                    # Detect forms if not provided
                    if not form_fields:
                        form_fields = await self._detect_forms_hybrid(page)

                    # Fill detected forms
                    results = await self._fill_form_fields(page, form_fields, cv_data)

                    # Take screenshot for verification
                    screenshot = await page.screenshot(full_page=True)
                    screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

                    processing_time = time.time() - start_time

                    logger.info(
                        f"Form filling completed: {results['fields_filled']} fields filled in {processing_time:.2f}s")

                    return {
                        'success': results['fields_filled'] > 0,
                        'url': url,
                        'fields_filled': results['fields_filled'],
                        'fields_attempted': len(form_fields),
                        'errors': results['errors'],
                        'screenshots': [screenshot_b64],
                        'processing_time': processing_time,
                        'timestamp': datetime.utcnow().isoformat()
                    }

                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Form filling failed: {e}")

            return {
                'success': False,
                'url': url,
                'error': str(e),
                'fields_filled': 0,
                'processing_time': processing_time,
                'timestamp': datetime.utcnow().isoformat()
            }
        finally:
            self.active_tasks -= 1

    async def upload_cv(self, url: str, cv_file_path: str, additional_data: Dict = None) -> Dict[str, Any]:
        """Upload CV file and fill additional form data"""
        start_time = time.time()
        self.active_tasks += 1

        try:
            logger.info(f"Starting CV upload to {url}")

            if not Path(cv_file_path).exists():
                raise FileNotFoundError(f"CV file not found: {cv_file_path}")

            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await self._create_context(browser)
                page = await context.new_page()

                try:
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(2000)

                    # Find and handle file upload
                    upload_success = await self._handle_file_upload(page, cv_file_path)

                    # Fill additional form data if provided
                    form_filled = False
                    if additional_data:
                        form_fields = await self._detect_forms_hybrid(page)
                        fill_results = await self._fill_form_fields(page, form_fields, additional_data)
                        form_filled = fill_results['fields_filled'] > 0

                    # Try to submit the form
                    submitted = await self._try_form_submission(page)

                    # Check for confirmation
                    confirmation_received = await self._check_submission_confirmation(page)

                    processing_time = time.time() - start_time

                    return {
                        'success': upload_success,
                        'url': url,
                        'upload_success': upload_success,
                        'form_filled': form_filled,
                        'submitted': submitted,
                        'confirmation_received': confirmation_received,
                        'processing_time': processing_time,
                        'timestamp': datetime.utcnow().isoformat()
                    }

                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"CV upload failed: {e}")

            return {
                'success': False,
                'url': url,
                'error': str(e),
                'processing_time': processing_time,
                'timestamp': datetime.utcnow().isoformat()
            }
        finally:
            self.active_tasks -= 1

    async def complete_job_application(self, job_listing: Dict, cv_data: Dict) -> Dict[str, Any]:
        """Complete a full job application process"""
        start_time = time.time()
        self.active_tasks += 1

        try:
            application_url = job_listing.get('application_url')
            if not application_url:
                raise ValueError("No application URL provided in job listing")

            logger.info(f"Starting job application for {job_listing.get('company')} - {job_listing.get('position')}")

            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await self._create_context(browser)
                page = await context.new_page()

                errors = []
                screenshots = []

                try:
                    # Navigate to application page
                    await page.goto(application_url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(3000)

                    # Take initial screenshot
                    screenshot = await page.screenshot(full_page=True)
                    screenshots.append(base64.b64encode(screenshot).decode('utf-8'))

                    # Upload CV if file path is provided
                    cv_uploaded = False
                    if cv_data.get('file_path'):
                        try:
                            cv_uploaded = await self._handle_file_upload(page, cv_data['file_path'])
                            if cv_uploaded:
                                logger.info("CV uploaded successfully")
                            else:
                                errors.append("Failed to upload CV file")
                        except Exception as e:
                            errors.append(f"CV upload error: {str(e)}")

                    # Detect and fill form fields
                    form_fields = await self._detect_forms_hybrid(page)
                    fill_results = await self._fill_form_fields(page, form_fields, cv_data)

                    # Take screenshot after filling
                    screenshot = await page.screenshot(full_page=True)
                    screenshots.append(base64.b64encode(screenshot).decode('utf-8'))

                    # Try to submit application
                    submitted = await self._try_form_submission(page)

                    if submitted:
                        await page.wait_for_timeout(3000)  # Wait for submission processing

                        # Take final screenshot
                        screenshot = await page.screenshot(full_page=True)
                        screenshots.append(base64.b64encode(screenshot).decode('utf-8'))

                        # Check for confirmation
                        confirmation_received = await self._check_submission_confirmation(page)
                    else:
                        confirmation_received = False
                        errors.append("Failed to submit application form")

                    # Determine if follow-up is required
                    follow_up_required = not confirmation_received or len(errors) > 0

                    processing_time = time.time() - start_time
                    application_successful = submitted and confirmation_received

                    logger.info(
                        f"Job application completed: success={application_successful}, time={processing_time:.2f}s")

                    return {
                        'success': application_successful,
                        'application_url': application_url,
                        'cv_uploaded': cv_uploaded,
                        'fields_filled': fill_results['fields_filled'],
                        'application_submitted': submitted,
                        'confirmation_received': confirmation_received,
                        'follow_up_required': follow_up_required,
                        'errors': errors,
                        'screenshots': screenshots,
                        'processing_time': processing_time,
                        'timestamp': datetime.utcnow().isoformat()
                    }

                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Job application failed: {e}")

            return {
                'success': False,
                'application_url': job_listing.get('application_url'),
                'error': str(e),
                'processing_time': processing_time,
                'timestamp': datetime.utcnow().isoformat()
            }
        finally:
            self.active_tasks -= 1

    async def _launch_browser(self, playwright):
        """Launch browser with anti-detection measures"""
        return await playwright.chromium.launch(
            headless=self.config.headless,
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
                '--password-store=basic',
                '--use-mock-keychain'
            ]
        )

    async def _create_context(self, browser):
        """Create browser context with randomized fingerprinting"""
        # Randomize user agent and viewport
        user_agent = random.choice(self.user_agents)
        viewport = random.choice(self.viewports)

        context = await browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
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

        # Inject anti-detection scripts
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

            // Add some randomness to make detection harder
            Math.random = () => 0.4871847406725814; // Fixed but non-obvious value
        """)

        return context

    async def _detect_forms_dom(self, page: Page) -> List[Dict]:
        """Detect forms using DOM analysis"""
        selectors = [
            'input[type="text"]', 'input[type="email"]', 'input[type="tel"]',
            'input[type="password"]', 'input[type="file"]', 'input[type="number"]',
            'input[type="date"]', 'input[type="url"]', 'input:not([type])',
            'textarea', 'select', '[contenteditable="true"]', '[role="textbox"]',
            '.file-upload', '.file-drop-zone', '[data-testid*="upload"]',
            '[aria-label*="upload"]'
        ]

        fields = []
        for selector in selectors:
            elements = await page.query_selector_all(selector)

            for element in elements:
                try:
                    field = await self._analyze_dom_element(element, selector)
                    if field and await self._is_element_visible(element):
                        fields.append(field)
                except Exception as e:
                    logger.debug(f"Error analyzing element {selector}: {e}")
                    continue

        return fields

    async def _detect_forms_visual(self, page: Page) -> List[Dict]:
        """Detect forms using visual analysis"""
        # Take screenshot for visual analysis
        screenshot = await page.screenshot(full_page=True)

        # Use computer vision to detect form-like elements
        # This is a simplified implementation - in practice, you'd use more sophisticated CV
        image = Image.open(io.BytesIO(screenshot))

        # Convert to OpenCV format
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Detect rectangular regions that might be form fields
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        visual_fields = []
        for i, contour in enumerate(contours):
            # Filter contours that look like form fields
            x, y, w, h = cv2.boundingRect(contour)

            # Form field heuristics: reasonable size, horizontal orientation
            if 50 < w < 600 and 20 < h < 80 and w > h:
                field = {
                    'element_id': f'visual_field_{i}',
                    'field_type': 'text',  # Default assumption
                    'label': '',
                    'placeholder': '',
                    'required': False,
                    'coordinates': (x, y, w, h),
                    'css_selector': '',
                    'xpath': '',
                    'confidence': 0.6,
                    'detection_method': 'visual'
                }
                visual_fields.append(field)

        return visual_fields

    async def _detect_forms_tab(self, page: Page) -> List[Dict]:
        """Detect forms using tab navigation"""
        fields = []
        visited_elements = set()

        # Start from beginning of page
        await page.keyboard.press('Home')
        await page.wait_for_timeout(500)

        # Tab through focusable elements
        for i in range(50):  # Limit to prevent infinite loops
            await page.keyboard.press('Tab')
            await page.wait_for_timeout(100)

            # Get currently focused element
            focused_info = await page.evaluate("""
                () => {
                    const element = document.activeElement;
                    if (!element) return null;

                    const rect = element.getBoundingClientRect();
                    return {
                        tagName: element.tagName,
                        type: element.type || '',
                        id: element.id || '',
                        name: element.name || '',
                        className: element.className || '',
                        placeholder: element.placeholder || '',
                        required: element.required || false,
                        offsetLeft: rect.x,
                        offsetTop: rect.y,
                        offsetWidth: rect.width,
                        offsetHeight: rect.height
                    };
                }
            """)

            if not focused_info:
                continue

            # Create unique identifier
            element_key = f"{focused_info['tagName']}_{focused_info.get('id', '')}_{focused_info.get('name', '')}_{focused_info['offsetLeft']}_{focused_info['offsetTop']}"

            if element_key in visited_elements:
                break  # We've cycled through all tabbable elements

            visited_elements.add(element_key)

            # Check if it's a form element
            if self._is_form_element_info(focused_info):
                field = self._create_field_from_focused_info(focused_info)
                if field:
                    fields.append(field)

        return fields

    async def _detect_forms_hybrid(self, page: Page) -> List[Dict]:
        """Combine multiple detection methods for best results"""
        dom_fields = await self._detect_forms_dom(page)
        tab_fields = await self._detect_forms_tab(page)

        # Merge and deduplicate fields
        all_fields = {}

        # Add DOM fields (highest confidence)
        for field in dom_fields:
            key = self._get_field_key(field)
            field['confidence'] = min(field.get('confidence', 0.8) + 0.2, 1.0)
            all_fields[key] = field

        # Add tab fields for elements missed by DOM
        for field in tab_fields:
            key = self._get_field_key(field)
            if key not in all_fields:
                all_fields[key] = field

        return list(all_fields.values())

    async def _analyze_dom_element(self, element, selector: str) -> Optional[Dict]:
        """Analyze a DOM element to create field information"""
        try:
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

            return {
                'element_id': props['id'] or f"element_{hash(css_selector)}",
                'field_type': self._classify_field_type(props),
                'label': props['label'],
                'placeholder': props['placeholder'],
                'required': props['required'],
                'coordinates': (props['x'], props['y'], props['width'], props['height']),
                'css_selector': css_selector,
                'xpath': xpath,
                'confidence': 0.9,
                'detection_method': 'dom'
            }

        except Exception as e:
            logger.debug(f"Error analyzing DOM element: {e}")
            return None

    async def _generate_css_selector(self, element) -> str:
        """Generate CSS selector for element"""
        return await element.evaluate("""
            (el) => {
                if (el.id) return '#' + el.id;

                let selector = el.tagName.toLowerCase();
                if (el.className) {
                    selector += '.' + el.className.split(' ').join('.');
                }

                if (el.name) selector += `[name="${el.name}"]`;
                if (el.type && el.type !== 'text') selector += `[type="${el.type}"]`;
                if (el.placeholder) selector += `[placeholder*="${el.placeholder.substring(0, 10)}"]`;

                return selector;
            }
        """)

    async def _generate_xpath(self, element) -> str:
        """Generate XPath selector for element"""
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

    async def _is_element_visible(self, element) -> bool:
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

    def _classify_field_type(self, props: Dict) -> str:
        """Classify field type based on properties"""
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

        field_type = props.get('type', 'text').lower()
        if field_type in type_mapping:
            return type_mapping[field_type]

        # Smart classification based on labels and placeholders
        text_content = f"{props.get('label', '')} {props.get('placeholder', '')}".lower()

        if any(word in text_content for word in ['email', 'e-mail']):
            return 'email'
        elif any(word in text_content for word in ['phone', 'mobile', 'tel']):
            return 'phone'
        elif any(word in text_content for word in ['name', 'first', 'last']):
            return 'name'
        elif any(word in text_content for word in ['company', 'organization']):
            return 'company'
        elif any(word in text_content for word in ['position', 'title', 'role']):
            return 'position'
        elif any(word in text_content for word in ['upload', 'file', 'resume', 'cv']):
            return 'file_upload'

        return 'text'

    def _is_form_element_info(self, element_info: Dict) -> bool:
        """Check if element info represents a form field"""
        form_tags = {'INPUT', 'TEXTAREA', 'SELECT'}
        form_types = {'text', 'email', 'tel', 'password', 'file', 'number', 'date', 'url'}

        if element_info['tagName'] in form_tags:
            if element_info['tagName'] == 'INPUT':
                return element_info.get('type', 'text') in form_types
            return True

        return False

    def _create_field_from_focused_info(self, focused_info: Dict) -> Optional[Dict]:
        """Create field dictionary from focused element info"""
        try:
            field_type = focused_info.get('type', 'text')
            if focused_info['tagName'] == 'TEXTAREA':
                field_type = 'textarea'
            elif focused_info['tagName'] == 'SELECT':
                field_type = 'select'

            css_selector = f"{focused_info['tagName'].lower()}"
            if focused_info.get('id'):
                css_selector = f"#{focused_info['id']}"
            elif focused_info.get('name'):
                css_selector += f"[name='{focused_info['name']}']"

            return {
                'element_id': focused_info.get('id', f"tab_element_{hash(str(focused_info))}"),
                'field_type': field_type,
                'label': focused_info.get('placeholder', ''),
                'placeholder': focused_info.get('placeholder', ''),
                'required': focused_info.get('required', False),
                'coordinates': (
                    focused_info['offsetLeft'],
                    focused_info['offsetTop'],
                    focused_info['offsetWidth'],
                    focused_info['offsetHeight']
                ),
                'css_selector': css_selector,
                'xpath': f"//{focused_info['tagName'].lower()}",
                'confidence': 0.7,
                'detection_method': 'tab'
            }
        except Exception:
            return None

    def _get_field_key(self, field: Dict) -> str:
        """Generate unique key for field deduplication"""
        coords = field.get('coordinates', (0, 0, 0, 0))
        return f"{field.get('field_type', 'unknown')}_{coords[0]}_{coords[1]}"

    def _serialize_field(self, field: Dict) -> Dict:
        """Serialize field for JSON storage"""
        return {
            'element_id': field.get('element_id', ''),
            'field_type': field.get('field_type', 'text'),
            'label': field.get('label', ''),
            'placeholder': field.get('placeholder', ''),
            'required': field.get('required', False),
            'coordinates': field.get('coordinates', (0, 0, 0, 0)),
            'css_selector': field.get('css_selector', ''),
            'xpath': field.get('xpath', ''),
            'confidence': field.get('confidence', 0.0),
            'detection_method': field.get('detection_method', 'unknown')
        }

    async def _fill_form_fields(self, page: Page, form_fields: List[Dict], cv_data: Dict) -> Dict:
        """Fill form fields with CV data"""
        fields_filled = 0
        errors = []

        for field in form_fields:
            try:
                value = self._get_field_value(field, cv_data)
                if not value:
                    continue

                success = await self._fill_single_field(page, field, value)
                if success:
                    fields_filled += 1
                    logger.debug(f"Filled field {field['element_id']} with value")
                else:
                    errors.append(f"Failed to fill field {field['element_id']}")

            except Exception as e:
                error_msg = f"Error filling field {field['element_id']}: {str(e)}"
                errors.append(error_msg)
                logger.debug(error_msg)

        return {
            'fields_filled': fields_filled,
            'errors': errors
        }

    async def _fill_single_field(self, page: Page, field: Dict, value: str) -> bool:
        """Fill a single form field"""
        try:
            # Try different selector strategies
            selectors = [field['css_selector'], field['xpath'], f"#{field['element_id']}"]
            element = None

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
            field_type = field.get('field_type', 'text')

            if field_type == 'file_upload':
                return await self._handle_file_input(element, value)
            elif field_type in ['select', 'dropdown']:
                return await self._handle_select_input(element, value)
            elif field_type == 'textarea':
                return await self._handle_textarea_input(page, element, value)
            else:
                return await self._handle_text_input(page, element, value)

        except Exception as e:
            logger.debug(f"Error filling field: {e}")
            return False

    async def _handle_text_input(self, page: Page, element, value: str) -> bool:
        """Handle text input with human-like typing"""
        try:
            await element.click()
            await element.fill('')  # Clear existing content

            # Human-like typing with random delays
            for char in value:
                await element.type(char)
                await page.wait_for_timeout(random.randint(50, 150))

            return True
        except:
            return False

    async def _handle_textarea_input(self, page: Page, element, value: str) -> bool:
        """Handle textarea input"""
        try:
            await element.click()
            await element.fill(value)
            return True
        except:
            return False

    async def _handle_select_input(self, element, value: str) -> bool:
        """Handle select dropdown input"""
        try:
            # Try to select by value, then by text
            try:
                await element.select_option(value=value)
            except:
                await element.select_option(label=value)
            return True
        except:
            return False

    async def _handle_file_input(self, element, file_path: str) -> bool:
        """Handle file input"""
        try:
            if Path(file_path).exists():
                await element.set_input_files(file_path)
                return True
        except:
            pass
        return False

    async def _handle_file_upload(self, page: Page, file_path: str) -> bool:
        """Handle file upload with multiple strategies"""
        try:
            # Strategy 1: Direct file input
            file_inputs = await page.query_selector_all('input[type="file"]')
            for file_input in file_inputs:
                try:
                    await file_input.set_input_files(file_path)
                    logger.info("File uploaded via direct input")
                    return True
                except:
                    continue

            # Strategy 2: Click upload button then handle file dialog
            upload_selectors = [
                'button:has-text("upload")',
                'button:has-text("choose")',
                'button:has-text("browse")',
                '.upload-btn',
                '.file-upload-btn',
                '[data-testid*="upload"]'
            ]

            for selector in upload_selectors:
                try:
                    upload_button = await page.query_selector(selector)
                    if upload_button:
                        # Set up file chooser handler
                        async with page.expect_file_chooser() as fc_info:
                            await upload_button.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(file_path)

                        logger.info("File uploaded via button click")
                        return True
                except:
                    continue

            return False

        except Exception as e:
            logger.debug(f"File upload error: {e}")
            return False

    async def _try_form_submission(self, page: Page) -> bool:
        """Try to submit the form"""
        try:
            # Look for submit buttons
            submit_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                'button:has-text("submit")',
                'button:has-text("apply")',
                'button:has-text("send")',
                '.submit-btn',
                '.apply-btn'
            ]

            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button and await self._is_element_visible(submit_button):
                        await submit_button.click()
                        logger.info("Form submitted")
                        return True
                except:
                    continue

            # Try Enter key on focused element
            try:
                await page.keyboard.press('Enter')
                return True
            except:
                pass

            return False

        except Exception as e:
            logger.debug(f"Form submission error: {e}")
            return False

    async def _check_submission_confirmation(self, page: Page) -> bool:
        """Check for submission confirmation"""
        try:
            # Wait a bit for page to process
            await page.wait_for_timeout(3000)

            # Look for success indicators
            success_indicators = [
                'text=thank you',
                'text=success',
                'text=submitted',
                'text=received',
                '.success-message',
                '.confirmation',
                '.thank-you'
            ]

            for indicator in success_indicators:
                try:
                    element = await page.query_selector(indicator)
                    if element:
                        logger.info("Submission confirmation found")
                        return True
                except:
                    continue

            # Check URL change (might redirect to confirmation page)
            current_url = page.url
            if 'success' in current_url.lower() or 'thank' in current_url.lower():
                return True

            return False

        except Exception as e:
            logger.debug(f"Confirmation check error: {e}")
            return False

    def _get_field_value(self, field: Dict, cv_data: Dict) -> str:
        """Get appropriate value for field from CV data"""
        field_type = field.get('field_type', 'text')
        label = field.get('label', '').lower()
        placeholder = field.get('placeholder', '').lower()

        # Direct field type mapping
        field_mapping = {
            'name': cv_data.get('name', ''),
            'email': cv_data.get('email', ''),
            'phone': cv_data.get('phone', ''),
            'company': cv_data.get('current_company', ''),
            'position': cv_data.get('title', ''),
            'textarea': cv_data.get('summary', '')
        }

        if field_type in field_mapping:
            return field_mapping[field_type]

        # Label-based mapping
        label_text = f"{label} {placeholder}"

        if any(word in label_text for word in ['first', 'given']):
            name_parts = cv_data.get('name', '').split()
            return name_parts[0] if name_parts else ''
        elif any(word in label_text for word in ['last', 'family', 'surname']):
            name_parts = cv_data.get('name', '').split()
            return name_parts[-1] if len(name_parts) > 1 else ''
        elif any(word in label_text for word in ['email', 'e-mail']):
            return cv_data.get('email', '')
        elif any(word in label_text for word in ['phone', 'mobile', 'tel']):
            return cv_data.get('phone', '')
        elif any(word in label_text for word in ['city', 'location']):
            return cv_data.get('location', '')
        elif any(word in label_text for word in ['experience', 'years']):
            return str(cv_data.get('experience_years', ''))
        elif any(word in label_text for word in ['skill', 'technology']):
            return ', '.join(cv_data.get('skills', [])[:5])  # First 5 skills
        elif any(word in label_text for word in ['summary', 'about', 'description']):
            return cv_data.get('summary', '')
        elif any(word in label_text for word in ['linkedin']):
            return cv_data.get('linkedin', '')
        elif any(word in label_text for word in ['github']):
            return cv_data.get('github', '')
        elif any(word in label_text for word in ['website', 'portfolio']):
            return cv_data.get('website', '')

        return ''