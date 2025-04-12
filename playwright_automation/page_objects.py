import os
import re
from datetime import datetime

from .prompts import get_page_analysis_prompt, get_page_object_prompt
from .utils import format_console_output

async def generate_page_objects(feature_data, test_cases):
    """
    Generate page objects needed for testing a feature based on test cases.
    Uses browser inspection to find reliable selectors.
    
    Args:
        feature_data (dict): The feature data
        test_cases (list): List of test cases for the feature
        
    Returns:
        list: List of page object names that were generated
    """
    print(format_console_output("info", f"Analyzing feature for page objects: {feature_data.get('name', 'Unknown')}"))
    
    # Ensure the pages directory exists
    pages_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "playwright_tests", "pages"))
    os.makedirs(pages_dir, exist_ok=True)
    
    # Create base page if it doesn't exist
    base_page_path = os.path.join(pages_dir, "BasePage.js")
    if not os.path.exists(base_page_path):
        with open(base_page_path, "w", encoding="utf-8") as f:
            f.write(generate_base_page())
        print(format_console_output("info", "Created BasePage.js"))
    
    # Analyze the feature and test cases to determine needed page objects
    needed_pages = await analyze_pages_needed(feature_data, test_cases)
    
    # Use browser inspection to find selectors
    from .browser_inspector import BrowserInspector
    
    # Only initialize browser if there are pages with elements to inspect
    pages_with_elements = any(page.get('elements') for page in needed_pages)
    
    if pages_with_elements:
        print(format_console_output("info", "Starting browser inspection for selectors"))
        browser_inspector = BrowserInspector()
        
        try:
            # Inspect all pages
            pages_with_selectors = await browser_inspector.inspect_all_pages(needed_pages)
            
            # Close the browser
            await browser_inspector.close()
            
            # Update the needed_pages with selectors
            for page in needed_pages:
                page_name = page.get('name')
                if page_name in pages_with_selectors:
                    page['elements_with_selectors'] = pages_with_selectors[page_name]['elements']
        
        except Exception as e:
            print(format_console_output("error", f"Browser inspection failed: {str(e)}"))
            print(format_console_output("warning", "Continuing with generic selectors"))
    
    # Generate each page object
    generated_pages = ["BasePage"]  # Always include BasePage
    
    for page_info in needed_pages:
        page_name = page_info["name"]
        page_path = os.path.join(pages_dir, f"{page_name}.js")
        
        # Check if page already exists
        if os.path.exists(page_path) and not page_info.get("force_update", False):
            print(format_console_output("info", f"Page object {page_name} already exists, skipping"))
            generated_pages.append(page_name)
            continue
        
        # Generate the page object
        page_content = await generate_page_class(page_info, feature_data, test_cases)
        
        # Save the page object
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_content)
        
        print(format_console_output("success", f"Generated page object: {page_name}"))
        generated_pages.append(page_name)
    
    return generated_pages
    
"""
Page object generation for Playwright tests.
This module handles creating and updating Page Object Model classes.
"""
async def generate_page_objects(feature_data, test_cases):
    """
    Generate page objects needed for testing a feature based on test cases.
    
    Args:
        feature_data (dict): The feature data
        test_cases (list): List of test cases for the feature
        
    Returns:
        list: List of page object names that were generated
    """
    print(format_console_output("info", f"Analyzing feature for page objects: {feature_data.get('name', 'Unknown')}"))
    
    # Ensure the pages directory exists
    pages_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "playwright_tests", "pages"))
    os.makedirs(pages_dir, exist_ok=True)
    
    # Create base page if it doesn't exist
    base_page_path = os.path.join(pages_dir, "BasePage.js")
    if not os.path.exists(base_page_path):
        with open(base_page_path, "w", encoding="utf-8") as f:
            f.write(generate_base_page())
        print(format_console_output("info", "Created BasePage.js"))
    
    # Analyze the feature and test cases to determine needed page objects
    needed_pages = await analyze_pages_needed(feature_data, test_cases)
    
    # Generate each page object
    generated_pages = ["BasePage"]  # Always include BasePage
    
    for page_info in needed_pages:
        page_name = page_info["name"]
        page_path = os.path.join(pages_dir, f"{page_name}.js")
        
        # Check if page already exists
        if os.path.exists(page_path) and not page_info.get("force_update", False):
            print(format_console_output("info", f"Page object {page_name} already exists, skipping"))
            generated_pages.append(page_name)
            continue
        
        # Generate the page object
        page_content = await generate_page_class(page_info, feature_data, test_cases)
        
        # Save the page object
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_content)
        
        print(format_console_output("success", f"Generated page object: {page_name}"))
        generated_pages.append(page_name)
    
    return generated_pages


async def analyze_pages_needed(feature_data, test_cases):
    """
    Analyze the feature and test cases to determine needed page objects.
    Uses AI to extract pages mentioned in test cases.
    
    Args:
        feature_data (dict): The feature data
        test_cases (list): List of test cases for the feature
        
    Returns:
        list: List of page object info dictionaries
    """
    from config.config import TestCaseAgent
    
    # Prepare the prompt
    from .prompts import get_browser_inspection_prompt
    prompt = get_browser_inspection_prompt(feature_data, test_cases)
    
    try:
        # Ask AI to analyze pages needed
        print(format_console_output("info", "Sending prompt to AI for page analysis..."))
        response = await TestCaseAgent.a_generate_reply(
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the response to extract page information
        import re
        import json
        
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                pages_data = json.loads(json_match.group(0))
                if isinstance(pages_data, dict) and "pages" in pages_data:
                    print(format_console_output("success", f"Identified {len(pages_data['pages'])} pages to inspect"))
                    return pages_data["pages"]
            except json.JSONDecodeError:
                pass
        
        # Fallback: Extract page names using regex pattern
        # Looking for Page names like "LoginPage", "EnvironmentPage", etc.
        page_matches = re.findall(r'(\w+Page)', response)
        
        # Deduplicate and format
        unique_pages = list(set(page_matches))
        
        # Create basic page info for each page
        pages_info = []
        for page_name in unique_pages:
            # Generate a path from the page name
            # e.g., "LoginPage" -> "/login"
            path = "/" + page_name.replace("Page", "").lower()
            
            pages_info.append({
                "name": page_name,
                "path": path,
                "elements": [],  # No elements identified
                "description": f"Page for {page_name.replace('Page', '')}"
            })
        
        print(format_console_output("success", f"Extracted {len(pages_info)} pages from analysis"))
        return pages_info
                
    except Exception as e:
        print(format_console_output("warning", f"Error in AI page analysis: {str(e)}"))
        # Fallback: Create a basic page based on the feature name
        feature_name = feature_data.get('name', 'Unknown').replace(' ', '')
        # Convert to pascal case and add Page suffix
        page_name = re.sub(r'(?:^|_)(.)', lambda m: m.group(1).upper(), feature_name)
        if not page_name.endswith('Page'):
            page_name += 'Page'
            
        return [{
            "name": page_name,
            "path": f"/{page_name.replace('Page', '').lower()}",
            "elements": [],
            "description": "Auto-generated from feature name"
        }]


async def generate_page_class(page_info, feature_data, test_cases):
    """
    Generate a page object class using AI.
    Enhanced to use selectors from browser inspection.
    
    Args:
        page_info (dict): Information about the page to generate
        feature_data (dict): The feature data
        test_cases (list): List of test cases for the feature
        
    Returns:
        str: The generated page object content
    """
    from config.config import TestCaseAgent
    
    page_name = page_info["name"]
    
    # Check if we have elements with selectors from browser inspection
    elements_with_selectors = page_info.get('elements_with_selectors', {})
    has_selectors = bool(elements_with_selectors)
    
    # Prepare the prompt
    prompt = get_page_object_prompt(page_info, feature_data, test_cases)
    
    # If we have selectors, add them to the prompt
    if has_selectors:
        # Format selectors information
        selectors_info = "\n\nBased on browser inspection, here are the elements and their selectors:\n\n"
        
        for element_name, element_info in elements_with_selectors.items():
            selectors_info += f"Element: {element_name}\n"
            selectors_info += f"Description: {element_info.get('description', '')}\n"
            selectors_info += f"Type: {element_info.get('type', '')}\n"
            selectors_info += "Selectors:\n"
            
            for selector_type, selector_value in element_info.get('selectors', {}).items():
                selectors_info += f"  - {selector_type}: {selector_value}\n"
            
            selectors_info += "\n"
        
        # Add to prompt
        prompt += selectors_info
        prompt += "\nUse these selectors in your page object class for more reliable element location."
    
    try:
        # Ask AI to generate the page object
        print(format_console_output("info", f"Sending prompt to AI for page object generation: {page_name}"))
        response = await TestCaseAgent.a_generate_reply(
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract the code from the response
        import re
        code_match = re.search(r'```javascript\s*([\s\S]*?)\s*```', response)
        if code_match:
            page_content = code_match.group(1).strip()
        else:
            page_content = response.strip()
        
        # If we have selectors but they're not in the generated code, try to inject them
        if has_selectors and "this.selectors" in page_content:
            # Check if we need to add the selectors
            needs_selectors = True
            
            for element_name in elements_with_selectors:
                if f"'{element_name}':" in page_content or f"\"{element_name}\":" in page_content:
                    # Element already exists in selectors
                    needs_selectors = False
                    break
            
            if needs_selectors:
                # Try to inject the selectors
                try:
                    # Find the selectors object
                    selectors_match = re.search(r'this\.selectors\s*=\s*\{([^}]*)\}', page_content)
                    if selectors_match:
                        # Extract existing selectors
                        existing_selectors = selectors_match.group(1)
                        
                        # Create new selectors
                        new_selectors = existing_selectors
                        
                        for element_name, element_info in elements_with_selectors.items():
                            selectors = element_info.get('selectors', {})
                            if selectors:
                                # Get the best selector
                                best_selector = None
                                for selector_type in ['id', 'testid', 'name', 'text', 'css', 'xpath']:
                                    if selector_type in selectors:
                                        best_selector = selectors[selector_type]
                                        break
                                
                                if best_selector:
                                    new_selectors += f",\n            {element_name}: '{best_selector}'"
                        
                        # Replace the selectors in the page content
                        page_content = page_content.replace(
                            f"this.selectors = {{{existing_selectors}}}",
                            f"this.selectors = {{{new_selectors}}}"
                        )
                except Exception as inject_e:
                    print(format_console_output("warning", f"Failed to inject selectors: {str(inject_e)}"))
        
        return page_content
        
    except Exception as e:
        print(format_console_output("error", f"Error in AI page object generation: {str(e)}"))
        # Generate a fallback page object
        return generate_fallback_page_object(page_info, feature_data)


def generate_base_page():
    """Generate the BasePage class."""
    return """/**
 * Base page object that contains common methods used across all pages.
 */
class BasePage {
    /**
     * @param {import('@playwright/test').Page} page
     */
    constructor(page) {
        this.page = page;
        this.baseUrl = process.env.BASE_URL || 'http://localhost:3000';
    }

    /**
     * Navigate to a specific path
     * @param {string} path Path to navigate to
     */
    async navigate(path) {
        await this.page.goto(`${this.baseUrl}${path}`);
    }

    /**
     * Wait for a specific timeout
     * @param {number} ms Milliseconds to wait
     */
    async wait(ms) {
        await this.page.waitForTimeout(ms);
    }

    /**
     * Click an element
     * @param {string} selector Element selector
     */
    async click(selector) {
        await this.page.click(selector);
    }

    /**
     * Fill a field with text
     * @param {string} selector Element selector
     * @param {string} text Text to fill
     */
    async fill(selector, text) {
        await this.page.fill(selector, text);
    }

    /**
     * Get text content of an element
     * @param {string} selector Element selector
     * @returns {Promise<string>} Text content
     */
    async getText(selector) {
        return await this.page.textContent(selector);
    }

    /**
     * Check if an element is visible
     * @param {string} selector Element selector
     * @returns {Promise<boolean>} True if visible
     */
    async isVisible(selector) {
        const element = await this.page.$(selector);
        if (!element) return false;
        return await element.isVisible();
    }

    /**
     * Wait for an element to be visible
     * @param {string} selector Element selector
     * @param {object} options Options for waiting
     */
    async waitForElement(selector, options = {}) {
        await this.page.waitForSelector(selector, { state: 'visible', ...options });
    }

    /**
     * Take a screenshot
     * @param {string} name Screenshot name
     */
    async takeScreenshot(name) {
        await this.page.screenshot({ path: `./screenshots/${name}.png` });
    }
}

module.exports = { BasePage };
"""


def generate_fallback_page_object(page_info, feature_data):
    """Generate a fallback page object if AI generation fails."""
    page_name = page_info["name"]
    feature_name = feature_data.get('name', 'Unknown')
    
    # Check if we have elements with selectors from browser inspection
    elements_with_selectors = page_info.get('elements_with_selectors', {})
    has_selectors = bool(elements_with_selectors)
    
    # Start with the basic template
    content = f"""/**
 * {page_name} - Page object for {feature_name}
 * Auto-generated fallback implementation
 */
const {{ BasePage }} = require('./BasePage');

class {page_name} extends BasePage {{
    /**
     * @param {{import('@playwright/test').Page}} page
     */
    constructor(page) {{
        super(page);
        
        // Define selectors for this page
        this.selectors = {{
"""
    
    # Add selectors from browser inspection if available
    if has_selectors:
        for element_name, element_info in elements_with_selectors.items():
            selectors = element_info.get('selectors', {})
            if selectors:
                # Get the best selector
                best_selector = None
                for selector_type in ['id', 'testid', 'name', 'text', 'css', 'xpath']:
                    if selector_type in selectors:
                        best_selector = selectors[selector_type]
                        break
                
                if best_selector:
                    content += f"            {element_name}: '{best_selector}',\n"
    
    # Add some default selectors if no browser inspection data
    if not has_selectors:
        content += """            // Example selectors - update these based on the actual application
            title: 'h1',
            createButton: 'button:has-text("Create")',
            editButton: 'button:has-text("Edit")',
            deleteButton: 'button:has-text("Delete")',
            nameInput: 'input[name="name"]',
            saveButton: 'button:has-text("Save")',
            cancelButton: 'button:has-text("Cancel")',
            confirmDialog: '.confirmation-dialog',
            confirmButton: '.confirmation-dialog button:has-text("Confirm")'
"""
    
    # Complete the selectors object
    content += "        };\n    }\n\n"
    
    # Add navigateTo method
    path = page_info.get('path', '/')
    content += f"""    /**
     * Navigate to this page
     */
    async navigateTo() {{
        // Navigate to the page
        await this.navigate('{path}');
    }}
"""
    
    # Add methods based on elements
    if has_selectors:
        # Group elements by type
        buttons = []
        inputs = []
        links = []
        others = []
        
        for element_name, element_info in elements_with_selectors.items():
            element_type = element_info.get('type', '')
            if element_type == 'button':
                buttons.append(element_name)
            elif element_type == 'input':
                inputs.append(element_name)
            elif element_type == 'link':
                links.append(element_name)
            else:
                others.append(element_name)
        
        # Add methods for buttons
        for button in buttons:
            method_name = f"click{button[0].upper()}{button[1:]}"
            if method_name.endswith('Button'):
                method_name = method_name[:-6]  # Remove 'Button' suffix
            
            content += f"""
    /**
     * Click the {button} button
     */
    async {method_name}() {{
        await this.click(this.selectors.{button});
    }}
"""
        
        # Add methods for inputs
        for input_el in inputs:
            method_name = f"fill{input_el[0].upper()}{input_el[1:]}"
            if method_name.endswith('Input'):
                method_name = method_name[:-5]  # Remove 'Input' suffix
            
            content += f"""
    /**
     * Fill the {input_el} input
     * @param {{string}} value The value to enter
     */
    async {method_name}(value) {{
        await this.fill(this.selectors.{input_el}, value);
    }}
"""
        
        # Add methods for links
        for link in links:
            method_name = f"click{link[0].upper()}{link[1:]}"
            if method_name.endswith('Link'):
                method_name = method_name[:-4]  # Remove 'Link' suffix
            
            content += f"""
    /**
     * Click the {link} link
     */
    async {method_name}() {{
        await this.click(this.selectors.{link});
    }}
"""
    else:
        # Add generic methods if no specific elements
        content += """
    /**
     * Create a new item
     * @param {{name: string}} data Item data
     */
    async createItem(data) {
        await this.click(this.selectors.createButton);
        await this.fill(this.selectors.nameInput, data.name);
        await this.click(this.selectors.saveButton);
    }

    /**
     * Edit an existing item
     * @param {{name: string}} data Updated item data
     */
    async editItem(data) {
        await this.click(this.selectors.editButton);
        await this.fill(this.selectors.nameInput, data.name);
        await this.click(this.selectors.saveButton);
    }

    /**
     * Delete an item
     * @returns {Promise<boolean>} True if delete was confirmed
     */
    async deleteItem() {
        await this.click(this.selectors.deleteButton);
        if (await this.isVisible(this.selectors.confirmDialog)) {
            await this.click(this.selectors.confirmButton);
            return true;
        }
        return false;
    }
"""
    
    # Close the class and add exports
    content += "}\n\nmodule.exports = { " + page_name + " };\n"
    
    return content