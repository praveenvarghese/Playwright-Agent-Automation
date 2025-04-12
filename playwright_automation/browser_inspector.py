"""
Browser inspector for Playwright test automation with enhanced debugging.
This module handles browser inspection to extract reliable selectors.
"""

import os
import json
import asyncio
import traceback
from dotenv import load_dotenv
from browser_use import BrowserConfig, Browser
from browser_use.browser.context import BrowserContextConfig, BrowserContext


def format_console_output(message_type, message):
    """
    Format console output with emojis for better visibility.
    """
    # Icons
    icons = {
        'info': '🔹',
        'success': '✅',
        'warning': '⚠️',
        'error': '❌',
        'debug': '🔍'
    }
    
    # Get the icon
    icon = icons.get(message_type.lower(), '•')
    
    # Return formatted message
    return f"{icon} {message}"


class BrowserInspector:
    def __init__(self):
        """Initialize browser inspector with configuration from environment variables."""
        print(format_console_output("debug", "BrowserInspector.__init__ started"))
        
        try:
            # Load environment variables
            load_dotenv()
            
            # Get configuration from environment
            self.app_url = os.getenv("APP_URL", "http://localhost:3000")
            self.app_username = os.getenv("APP_USERNAME", "")
            self.app_password = os.getenv("APP_PASSWORD", "")
            self.app_headless = os.getenv("APP_HEADLESS", "true").lower() == "true"
            
            print(format_console_output("debug", f"Environment loaded. URL: {self.app_url}, Headless: {self.app_headless}"))
            
            # Configure browser
            print(format_console_output("debug", "Creating BrowserConfig"))
            browser_config = BrowserConfig(
                headless=self.app_headless,
                disable_security=True
            )
            
            # Define browser context configuration
            print(format_console_output("debug", "Creating BrowserContextConfig"))
            context_config = BrowserContextConfig(
                wait_for_network_idle_page_load_time=3.0,
                browser_window_size={'width': 1280, 'height': 1100},
                locale='en-US',
                highlight_elements=True,
                viewport_expansion=500,
            )
            
            # Initialize browser and context
            print(format_console_output("debug", "Initializing Browser"))
            self.browser = Browser(config=browser_config)
            print(format_console_output("debug", "Initializing BrowserContext"))
            self.context = BrowserContext(browser=self.browser, config=context_config)
            
            # Store page objects
            self.pages = {}
            
            print(format_console_output("info", "Browser inspector initialized"))
            
        except Exception as e:
            print(format_console_output("error", f"Error initializing BrowserInspector: {str(e)}"))
            traceback.print_exc()
            # Re-raise the exception to ensure caller knows initialization failed
            raise
    
    async def login(self):
        """
        Login to the application.
        
        Returns:
            page: The browser page after login
        """
        print(format_console_output("debug", "login() method started"))
        try:
            print(format_console_output("info", f"Logging in to {self.app_url}"))
            
            # Create a new page
            print(format_console_output("debug", "Creating new page"))
            page = await self.context.new_page()
            print(format_console_output("debug", "Page created successfully"))
            
            print(format_console_output("debug", f"Navigating to {self.app_url}"))
            await page.goto(self.app_url)
            print(format_console_output("debug", "Navigation completed"))
            
            # Check if login is required
            if not self.app_username or not self.app_password:
                print(format_console_output("warning", "No credentials provided. Assuming no login required."))
                return page
            
            # Look for common login form elements
            username_selectors = [
                'input[name="username"]', 
                'input[name="email"]', 
                'input[type="email"]',
                '#username',
                '#email'
            ]
            
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                '#password'
            ]
            
            # Find and fill username field
            username_filled = False
            for selector in username_selectors:
                print(format_console_output("debug", f"Trying username selector: {selector}"))
                if await page.is_visible(selector):
                    print(format_console_output("debug", f"Username field found with selector: {selector}"))
                    await page.fill(selector, self.app_username)
                    username_filled = True
                    break
            
            if not username_filled:
                print(format_console_output("warning", "Could not find username field. Login may fail."))
            
            # Find and fill password field
            password_filled = False
            for selector in password_selectors:
                print(format_console_output("debug", f"Trying password selector: {selector}"))
                if await page.is_visible(selector):
                    print(format_console_output("debug", f"Password field found with selector: {selector}"))
                    await page.fill(selector, self.app_password)
                    password_filled = True
                    break
            
            if not password_filled:
                print(format_console_output("warning", "Could not find password field. Login may fail."))
            
            # Find and click login button
            login_button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'button:has-text("Signin")',
                'input[value="Log In"]',
                'input[value="Login"]',
                'input[value="Sign In"]',
                'input[value="Signin"]'
            ]
            
            login_clicked = False
            for selector in login_button_selectors:
                print(format_console_output("debug", f"Trying login button selector: {selector}"))
                if await page.is_visible(selector):
                    print(format_console_output("debug", f"Login button found with selector: {selector}"))
                    await page.click(selector)
                    login_clicked = True
                    break
            
            if not login_clicked:
                print(format_console_output("warning", "Could not find login button. Login may fail."))
            
            # Wait for navigation to complete
            print(format_console_output("debug", "Waiting for navigation to complete"))
            await page.wait_for_load_state('networkidle')
            
            print(format_console_output("success", "Login completed"))
            return page
            
        except Exception as e:
            print(format_console_output("error", f"Login failed: {str(e)}"))
            traceback.print_exc()
            # Return a page anyway so we can continue
            print(format_console_output("debug", "Creating new page after login error"))
            return await self.context.new_page()
    
    async def navigate_to_page(self, page, path):
        """
        Navigate to a specific page in the application.
        
        Args:
            page: The browser page
            path: The path to navigate to
        
        Returns:
            bool: True if navigation succeeded, False otherwise
        """
        print(format_console_output("debug", f"navigate_to_page() started with path: {path}"))
        try:
            print(format_console_output("info", f"Navigating to {path}"))
            
            # Ensure path starts with /
            if not path.startswith('/'):
                path = '/' + path
                print(format_console_output("debug", f"Adjusted path to: {path}"))
            
            # Navigate to the page
            url = self.app_url + path
            print(format_console_output("debug", f"Full URL: {url}"))
            await page.goto(url)
            
            # Wait for navigation to complete
            print(format_console_output("debug", "Waiting for navigation to complete"))
            await page.wait_for_load_state('networkidle')
            
            print(format_console_output("success", f"Navigation to {path} completed"))
            return True
            
        except Exception as e:
            print(format_console_output("error", f"Navigation failed: {str(e)}"))
            traceback.print_exc()
            return False
    
    async def find_element_selectors(self, page, element_info):
        """
        Find selectors for an element based on its description.
        
        Args:
            page: The browser page
            element_info: Dictionary with element information
        
        Returns:
            dict: Dictionary of selectors (css, xpath, text, etc.)
        """
        print(format_console_output("debug", f"find_element_selectors() started"))
        try:
            element_name = element_info.get('name', 'unknown')
            element_type = element_info.get('type', 'unknown')
            element_text = element_info.get('text', '')
            element_description = element_info.get('description', '')
            
            print(format_console_output("info", f"Finding selectors for {element_name}: {element_description}"))
            print(format_console_output("debug", f"Element type: {element_type}, Element text: {element_text}"))
            
            # Start with an empty selectors dictionary
            selectors = {}
            
            # Create selectors based on element type
            if element_type == 'button':
                print(format_console_output("debug", "Processing button element"))
                # Text-based selectors
                if element_text:
                    selectors['text'] = f"button:has-text('{element_text}')"
                    selectors['xpath'] = f"//button[contains(text(), '{element_text}')]"
                    print(format_console_output("debug", f"Created text-based selectors: {selectors}"))
                
                # Try to find the element by text
                if element_text:
                    text_selector = f"button:has-text('{element_text}')"
                    print(format_console_output("debug", f"Checking if element is visible with selector: {text_selector}"))
                    is_visible = await page.is_visible(text_selector)
                    print(format_console_output("debug", f"Element visibility: {is_visible}"))
                    
                    if is_visible:
                        print(format_console_output("debug", "Getting more specific selectors"))
                        # Get more specific selectors
                        el = await page.query_selector(f"button:has-text('{element_text}')")
                        if el:
                            print(format_console_output("debug", "Element found, getting attributes"))
                            # Try to get ID
                            id_attr = await el.get_attribute('id')
                            if id_attr:
                                selectors['id'] = f"#{id_attr}"
                                print(format_console_output("debug", f"Found ID selector: {selectors['id']}"))
                            
                            # Try to get data-testid
                            testid_attr = await el.get_attribute('data-testid')
                            if testid_attr:
                                selectors['testid'] = f"[data-testid='{testid_attr}']"
                                print(format_console_output("debug", f"Found test ID selector: {selectors['testid']}"))
                            
                            # Try to get class
                            class_attr = await el.get_attribute('class')
                            if class_attr:
                                classes = class_attr.split()
                                if classes:
                                    selectors['class'] = f".{classes[0]}"
                                    print(format_console_output("debug", f"Found class selector: {selectors['class']}"))
                
            elif element_type == 'input':
                print(format_console_output("debug", "Processing input element"))
                # Try different input selectors
                selectors['name'] = f"input[name='{element_name}']"
                selectors['placeholder'] = f"input[placeholder='{element_text}']"
                selectors['xpath'] = f"//input[@placeholder='{element_text}']"
                print(format_console_output("debug", f"Created input selectors: {selectors}"))
                
                # Try to find the element by name or placeholder
                selector = f"input[name='{element_name}'], input[placeholder='{element_text}']"
                print(format_console_output("debug", f"Checking for input with selector: {selector}"))
                el = await page.query_selector(selector)
                if el:
                    print(format_console_output("debug", "Input element found, getting attributes"))
                    # Try to get ID
                    id_attr = await el.get_attribute('id')
                    if id_attr:
                        selectors['id'] = f"#{id_attr}"
                        print(format_console_output("debug", f"Found ID selector: {selectors['id']}"))
                    
                    # Try to get data-testid
                    testid_attr = await el.get_attribute('data-testid')
                    if testid_attr:
                        selectors['testid'] = f"[data-testid='{testid_attr}']"
                        print(format_console_output("debug", f"Found test ID selector: {selectors['testid']}"))
            
            elif element_type == 'link':
                print(format_console_output("debug", "Processing link element"))
                # Text-based selectors
                if element_text:
                    selectors['text'] = f"a:has-text('{element_text}')"
                    selectors['xpath'] = f"//a[contains(text(), '{element_text}')]"
                    print(format_console_output("debug", f"Created link selectors: {selectors}"))
                
                # Try to find the element by text
                if element_text:
                    text_selector = f"a:has-text('{element_text}')"
                    print(format_console_output("debug", f"Checking if link is visible with selector: {text_selector}"))
                    is_visible = await page.is_visible(text_selector)
                    print(format_console_output("debug", f"Link visibility: {is_visible}"))
                    
                    if is_visible:
                        print(format_console_output("debug", "Getting more specific selectors for link"))
                        # Get more specific selectors
                        el = await page.query_selector(text_selector)
                        if el:
                            print(format_console_output("debug", "Link found, getting attributes"))
                            # Try to get href
                            href_attr = await el.get_attribute('href')
                            if href_attr:
                                selectors['href'] = f"a[href='{href_attr}']"
                                print(format_console_output("debug", f"Found href selector: {selectors['href']}"))
            
            # If no selectors found, try generic text-based selectors
            if not selectors and element_text:
                print(format_console_output("debug", "No specific selectors found, trying generic text selectors"))
                selectors['generic_text'] = f":text('{element_text}')"
                selectors['generic_xpath'] = f"//*[contains(text(), '{element_text}')]"
            
            # If still no selectors, create fallback based on description
            if not selectors:
                print(format_console_output("debug", "Creating fallback selectors based on description"))
                # Create a sanitized version of the description for use in selectors
                sanitized = element_description.lower().replace(' ', '-')
                selectors['fallback'] = f"[data-testid='{sanitized}'], [id='{sanitized}'], [name='{sanitized}']"
                selectors['fallback_xpath'] = f"//*[contains(@id, '{sanitized}') or contains(@name, '{sanitized}') or contains(@data-testid, '{sanitized}')]"
            
            print(format_console_output("success", f"Found {len(selectors)} selectors for {element_name}"))
            print(format_console_output("debug", f"Selectors: {selectors}"))
            return selectors
            
        except Exception as e:
            print(format_console_output("error", f"Error finding selectors: {str(e)}"))
            traceback.print_exc()
            # Return a generic fallback selector
            sanitized = element_info.get('name', 'unknown').lower()
            fallback_selectors = {
                'fallback': f"[data-testid='{sanitized}'], [id='{sanitized}'], [name='{sanitized}']",
                'generic': f"button, input, a, div, span" # Very generic fallback
            }
            print(format_console_output("debug", f"Using fallback selectors: {fallback_selectors}"))
            return fallback_selectors
    
    async def inspect_page_elements(self, page_info):
        """
        Inspect all elements for a page.
        
        Args:
            page_info: Dictionary with page information including elements to inspect
        
        Returns:
            dict: Dictionary of page elements with their selectors
        """
        print(format_console_output("debug", f"inspect_page_elements() started"))
        try:
            page_name = page_info.get('name', 'UnknownPage')
            page_path = page_info.get('path', '/')
            elements = page_info.get('elements', [])
            
            print(format_console_output("info", f"Inspecting page: {page_name} at {page_path}"))
            print(format_console_output("debug", f"Elements to inspect: {len(elements)}"))
            
            # Login and navigate to the page
            print(format_console_output("debug", "Starting login process"))
            page = await self.login()
            print(format_console_output("debug", "Login completed, navigating to page"))
            navigation_success = await self.navigate_to_page(page, page_path)
            
            if not navigation_success:
                print(format_console_output("warning", f"Navigation to {page_path} failed. Using best-effort selectors."))
            
            # Find selectors for each element
            elements_with_selectors = {}
            
            for element_info in elements:
                element_name = element_info.get('name', 'unknown')
                print(format_console_output("debug", f"Processing element: {element_name}"))
                
                if navigation_success:
                    # Try to find real selectors
                    print(format_console_output("debug", f"Finding selectors for element: {element_name}"))
                    selectors = await self.find_element_selectors(page, element_info)
                else:
                    # Use generic selectors
                    print(format_console_output("debug", f"Using generic selectors for element: {element_name}"))
                    element_type = element_info.get('type', 'unknown')
                    element_text = element_info.get('text', '')
                    
                    if element_type == 'button' and element_text:
                        selectors = {
                            'text': f"button:has-text('{element_text}')",
                            'xpath': f"//button[contains(text(), '{element_text}')]"
                        }
                    elif element_type == 'input':
                        selectors = {
                            'name': f"input[name='{element_name}']",
                        }
                    elif element_type == 'link' and element_text:
                        selectors = {
                            'text': f"a:has-text('{element_text}')",
                            'xpath': f"//a[contains(text(), '{element_text}')]"
                        }
                    else:
                        # Generic fallback
                        sanitized = element_name.lower()
                        selectors = {
                            'fallback': f"[data-testid='{sanitized}'], [id='{sanitized}'], [name='{sanitized}']"
                        }
                    
                    print(format_console_output("debug", f"Generic selectors: {selectors}"))
                
                # Store the element with its selectors
                elements_with_selectors[element_name] = {
                    'description': element_info.get('description', ''),
                    'type': element_info.get('type', 'unknown'),
                    'selectors': selectors
                }
            
            # Close the page
            print(format_console_output("debug", "Closing page"))
            await page.close()
            
            print(format_console_output("success", f"Inspected {len(elements_with_selectors)} elements for {page_name}"))
            return elements_with_selectors
            
        except Exception as e:
            print(format_console_output("error", f"Error inspecting page elements: {str(e)}"))
            traceback.print_exc()
            return {}
    
    async def inspect_all_pages(self, pages_info):
        """
        Inspect all pages and their elements.
        
        Args:
            pages_info: List of page information dictionaries
        
        Returns:
            dict: Dictionary of pages with their elements and selectors
        """
        print(format_console_output("debug", f"inspect_all_pages() started"))
        try:
            print(format_console_output("info", f"Starting inspection of {len(pages_info)} pages"))
            
            # Dictionary to store all page information
            all_pages = {}
            
            # Process each page
            for page_info in pages_info:
                page_name = page_info.get('name', 'UnknownPage')
                print(format_console_output("debug", f"Starting inspection of page: {page_name}"))
                
                # Inspect this page
                elements = await self.inspect_page_elements(page_info)
                
                # Store the page information
                all_pages[page_name] = {
                    'path': page_info.get('path', '/'),
                    'elements': elements
                }
            
            print(format_console_output("success", f"Completed inspection of {len(all_pages)} pages"))
            return all_pages
            
        except Exception as e:
            print(format_console_output("error", f"Error inspecting pages: {str(e)}"))
            traceback.print_exc()
            return {}
    
    async def close(self):
        """Close the browser."""
        print(format_console_output("debug", "close() method started"))
        try:
            await self.browser.close()
            print(format_console_output("info", "Browser closed"))
        except Exception as e:
            print(format_console_output("error", f"Error closing browser: {str(e)}"))
            traceback.print_exc()


# Example usage
async def example_usage():
    inspector = BrowserInspector()
    
    # Example page information
    pages_info = [
        {
            "name": "LoginPage",
            "path": "/login",
            "elements": [
                {
                    "name": "username",
                    "description": "Username input field",
                    "type": "input",
                    "text": "Username"
                },
                {
                    "name": "password",
                    "description": "Password input field",
                    "type": "input",
                    "text": "Password"
                },
                {
                    "name": "loginButton",
                    "description": "Login button",
                    "type": "button",
                    "text": "Log In"
                }
            ]
        }
    ]
    
    # Inspect all pages
    pages = await inspector.inspect_all_pages(pages_info)
    
    # Print the results
    print(json.dumps(pages, indent=2))
    
    # Close the browser
    await inspector.close()


if __name__ == "__main__":
    asyncio.run(example_usage())