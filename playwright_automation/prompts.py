"""
AI prompts loader for Playwright test generation.
This module loads prompts from external text files.
"""

import os


def _load_prompt_template(filename):
    """
    Load a prompt template from a file.
    
    Args:
        filename (str): The filename of the prompt template
        
    Returns:
        str: The prompt template content or empty string if file not found
    """
    # Define the prompts directory path
    prompts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                 "..", "playwright_prompts"))
    
    # Check if prompts directory exists, create if not
    if not os.path.exists(prompts_dir):
        os.makedirs(prompts_dir)
    
    # Full path to the prompt file
    prompt_path = os.path.join(prompts_dir, filename)
    
    # Check if the file exists
    if not os.path.exists(prompt_path):
        # Create the default prompt file
        default_prompt = _get_default_prompt(filename)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(default_prompt)
        return default_prompt
    
    # Load the prompt from the file
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def _get_default_prompt(filename):
    """
    Get the default content for a prompt file if it doesn't exist.
    
    Args:
        filename (str): The filename of the prompt template
        
    Returns:
        str: The default prompt content
    """
    defaults = {
        "page_analysis.txt": """You are an expert in Playwright test automation and the Page Object Model pattern.

Based on the feature description and test cases below, identify the pages needed for implementing automation tests using the Page Object Model pattern.

Feature: {feature_name}
Description: {feature_description}

Test Cases:
{test_cases_text}

Analyze the above information and identify:
1. The main pages that would need to be modeled as Page Objects
2. For each page, suggest key UI elements and actions based on the test cases

Format your response as a JSON object with the following structure:
{
  "pages": [
    {
      "name": "PageName", // Should end with 'Page', e.g., "LoginPage" 
      "description": "Brief description of what this page represents",
      "elements": ["list", "of", "key", "UI", "elements"],
      "actions": ["list", "of", "key", "actions"]
    }
  ]
}

Examples of good page object names: LoginPage, EnvironmentPage, DashboardPage, etc.""",

        "page_object.txt": """You are an expert in Playwright test automation and the Page Object Model pattern.

Your task is to create a JavaScript Page Object class called '{page_name}' for a web application feature.

Feature: {feature_name}
Description: {feature_description}

Page Description: {page_description}

Test Cases that use this page:
{test_cases_text}

Create a high-quality Page Object class that:
1. Follows the Page Object Model pattern
2. Extends from BasePage
3. Includes all necessary selectors based on the test cases
4. Provides methods for all actions needed to implement the test cases
5. Includes proper JSDoc comments for methods and parameters
6. Uses best practices for Playwright automation

BasePage already provides these methods that you can use:
- navigate(path): Navigate to a specific path
- click(selector): Click an element
- fill(selector, text): Fill a field with text
- getText(selector): Get text from an element
- isVisible(selector): Check if an element is visible
- waitForElement(selector, options): Wait for an element to be visible
- takeScreenshot(name): Take a screenshot

Return the JavaScript code for the page object, formatted as follows:

```javascript
/**
 * {page_name} - [Brief description of what this page represents]
 */
const {{ BasePage }} = require('./BasePage');

class {page_name} extends BasePage {{
    /**
     * @param {{import('@playwright/test').Page}} page
     */
    constructor(page) {{
        super(page);
        
        // Define selectors for UI elements
        this.selectors = {{
            // Your selectors here
        }};
    }}
    
    // Your methods here
}}

module.exports = {{ {page_name} }};
```""",

        "test_script.txt": """You are an expert in Playwright test automation using the Page Object Model pattern.

Your task is to create a Playwright test script for the following test case:

Test Case ID: {test_case_id}
Title: {test_case_title}

Steps:
{test_case_steps}

Expected Results:
{test_case_expected_results}

Generate a complete Playwright test script that:
1. Follows the Page Object Model pattern
2. Uses the following page objects: {page_objects}
3. Implements all the test steps
4. Includes proper assertions for the expected results
5. Follows Playwright best practices
6. Includes comments explaining key steps

Each test should import the necessary page objects and use them to interact with the application.

Return only the JavaScript code for the test, formatted as follows:

```javascript
// {test_case_id}: {test_case_title}
const {{ test, expect }} = require('@playwright/test');
// Import page objects
const {{ PageName }} = require('../pages/PageName');

test('{test_case_title}', async ({ page }) => {{
    // Initialize page objects
    const pageObj = new PageName(page);
    
    // Implement test steps
    await pageObj.someMethod();
    
    // Assert expected results
    await expect(page.locator('selector')).toBeVisible();
}});
```""",

        "script_critic.txt": """You are an expert QA engineer specializing in Playwright automation and the Page Object Model pattern.

Review the following test script and provide feedback to improve it:

Test Case: {test_case_id}
Title: {test_case_title}

Original Steps:
{test_case_steps}

Expected Results:
{test_case_expected_results}

Generated Script:
```javascript
{script_content}
```

Please analyze the script for:
1. Correctness - Does it implement all steps from the test case?
2. Completeness - Does it verify all expected results?
3. POM Usage - Does it properly use the Page Object Model pattern?
4. Best Practices - Does it follow Playwright best practices?
5. Reliability - Are there potential flakiness issues?

Format your response as follows:
1. Issues (list specific problems that need to be fixed)
2. Suggested Improvements (specific code changes to improve the script)
3. Revised Script (provide a complete corrected version of the script)"""
    }
    
    return defaults.get(filename, "# No default content available for this prompt")


def get_page_analysis_prompt(feature_data, test_cases):
    """
    Create a prompt for AI to analyze which pages are needed for testing a feature.
    
    Args:
        feature_data (dict): The feature data
        test_cases (list): List of test cases for the feature
        
    Returns:
        str: The AI prompt
    """
    # Extract relevant information
    feature_name = feature_data.get('name', 'Unknown')
    feature_description = feature_data.get('description', '')
    
    # Format test cases
    test_cases_text = "\n\n".join([
        f"Test Case: {tc.get('id')}\n"
        f"Title: {tc.get('title', 'Unknown')}\n"
        f"Steps:\n{tc.get('steps', 'No steps available')}\n"
        f"Expected Results:\n{tc.get('expectedResults', 'No expected results available')}"
        for tc in test_cases[:5]  # Limit to 5 test cases to avoid overwhelming the prompt
    ])
    
    # Load template and format
    template = _load_prompt_template("page_analysis.txt")
    return template.format(
        feature_name=feature_name,
        feature_description=feature_description,
        test_cases_text=test_cases_text
    )

def get_test_script_prompt(test_case, page_objects, feature_data=None):
    """
    Create a prompt for AI to generate a test script.
    
    Args:
        test_case (dict): The test case to generate a script for
        page_objects (list): List of available page objects
        feature_data (dict, optional): The feature data
        
    Returns:
        str: The AI prompt
    """
    # Extract test case information
    test_case_id = test_case.get('id', 'unknown')
    test_case_title = test_case.get('title', 'Unknown Test Case')
    test_case_steps = test_case.get('steps', 'No steps available')
    test_case_expected_results = test_case.get('expectedResults', 'No expected results available')
    
    # Format the page objects list
    page_objects_text = ", ".join(page_objects)
    
    # Load template and format
    template = _load_prompt_template("test_script.txt")
    return template.format(
        test_case_id=test_case_id,
        test_case_title=test_case_title,
        test_case_steps=test_case_steps,
        test_case_expected_results=test_case_expected_results,
        page_objects=page_objects_text
    )

def get_browser_inspection_prompt(feature_data, test_cases):
    """
    Create a prompt for AI to analyze which pages and elements need browser inspection.
    
    Args:
        feature_data (dict): The feature data
        test_cases (list): List of test cases for the feature
        
    Returns:
        str: The AI prompt
    """
    # Extract relevant information
    feature_name = feature_data.get('name', 'Unknown')
    feature_description = feature_data.get('description', '')
    
    # Format test cases
    test_cases_text = "\n\n".join([
        f"Test Case: {tc.get('id')}\n"
        f"Title: {tc.get('title', 'Unknown')}\n"
        f"Steps:\n{tc.get('steps', 'No steps available')}\n"
        f"Expected Results:\n{tc.get('expectedResults', 'No expected results available')}"
        for tc in test_cases[:5]  # Limit to 5 test cases to avoid overwhelming the prompt
    ])
    
    # Create the prompt
    prompt = f"""You are an expert in identifying UI elements for web test automation.

Feature: {feature_name}
Description: {feature_description}

Test Cases:
{test_cases_text}

Based on the feature description and test cases, identify:
1. The pages that would need to be accessed for testing
2. For each page, the UI elements that would need to be interacted with

Format your response as a JSON object with this structure:
{{
  "pages": [
    {{
      "name": "PageName", // Should end with 'Page', e.g., "LoginPage"
      "path": "/path/to/page", // URL path to the page
      "description": "Brief description of the page",
      "elements": [
        {{
          "name": "elementName", // camelCase, e.g., "loginButton"
          "description": "What this element does",
          "type": "button|input|link|dropdown|checkbox|radio|text", // Element type
          "text": "Element text or label" // Visible text that helps identify the element
        }}
      ]
    }}
  ]
}}

Analyze the test steps carefully to identify each page and interactive element needed."""
    
    return prompt

def get_page_object_prompt(page_info, feature_data, test_cases):
    """
    Create a prompt for AI to generate a page object class.
    
    Args:
        page_info (dict): Information about the page to generate
        feature_data (dict): The feature data
        test_cases (list): List of test cases for the feature
        
    Returns:
        str: The AI prompt
    """
    # Extract relevant information
    page_name = page_info["name"]
    page_description = page_info.get("description", "")
    feature_name = feature_data.get('name', 'Unknown')
    feature_description = feature_data.get('description', '')
    
    # Format test cases related to this page (if we have that information)
    # Otherwise use all test cases
    test_cases_text = "\n\n".join([
        f"Test Case: {tc.get('id')}\n"
        f"Title: {tc.get('title', 'Unknown')}\n"
        f"Steps:\n{tc.get('steps', 'No steps available')}\n"
        f"Expected Results:\n{tc.get('expectedResults', 'No expected results available')}"
        for tc in test_cases[:5]  # Limit to 5 test cases to avoid overwhelming the prompt
    ])
    
    # Load template and format
    template = _load_prompt_template("page_object.txt")
    return template.format(
        page_name=page_name,
        page_description=page_description,
        feature_name=feature_name,
        feature_description=feature_description,
        test_cases_text=test_cases_text
    )