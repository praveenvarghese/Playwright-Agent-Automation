
import os
from .prompts import _load_prompt_template
from .utils import format_console_output

async def generate_test_script(test_case, page_objects, feature_data):
    """
    Generate a Playwright test script using AI.
    Enhanced to include information about available page objects and selectors.
    
    Args:
        test_case (dict): The test case to generate a script for
        page_objects (list): List of available page objects
        feature_data (dict): The feature data
        
    Returns:
        str: The generated test script content
    """
    from config.config import TestCaseAgent
    
    # Get the prompt template
    from .prompts import _load_prompt_template
    template = _load_prompt_template("test_script.txt")
    
    # Extract test case information
    test_case_id = test_case.get('id', 'unknown')
    test_case_title = test_case.get('title', 'Unknown Test Case')
    test_case_steps = test_case.get('steps', 'No steps available')
    test_case_expected_results = test_case.get('expectedResults', 'No expected results available')
    
    # Format the page objects list
    page_objects_text = ", ".join(page_objects)
    
    # Attempt to extract selectors from page objects to provide better context
    try:
        pages_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "playwright_tests", "pages"))
        page_object_selectors = {}
        
        for page_name in page_objects:
            page_path = os.path.join(pages_dir, f"{page_name}.js")
            if os.path.exists(page_path):
                with open(page_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Extract selectors from the page object
                import re
                selectors_match = re.search(r'this\.selectors\s*=\s*\{([\s\S]*?)\};', content)
                if selectors_match:
                    selector_text = selectors_match.group(1).strip()
                    page_object_selectors[page_name] = selector_text
                
                # Also try to extract methods to provide even better context
                methods = []
                method_matches = re.finditer(r'async\s+(\w+)\s*\([^)]*\)\s*\{', content)
                for match in method_matches:
                    method_name = match.group(1)
                    if method_name != 'constructor' and method_name not in methods:
                        methods.append(method_name)
                
                if methods:
                    page_object_selectors[f"{page_name}_methods"] = ", ".join(methods)
        
        # Add page object information to the prompt if available
        page_objects_info = "\n\nThese page objects are available for your test:\n\n"
        
        for page_name in page_objects:
            page_objects_info += f"## {page_name}\n"
            
            # Add methods if available
            if f"{page_name}_methods" in page_object_selectors:
                page_objects_info += f"Methods: {page_object_selectors[f'{page_name}_methods']}\n\n"
            
            # Add selectors if available
            if page_name in page_object_selectors:
                page_objects_info += f"Selectors:\n```javascript\n{{\n{page_object_selectors[page_name]}\n}}\n```\n\n"
        
        # Add this information to the prompt
        enhanced_prompt = template.format(
            test_case_id=test_case_id,
            test_case_title=test_case_title,
            test_case_steps=test_case_steps,
            test_case_expected_results=test_case_expected_results,
            page_objects=page_objects_text
        )
        
        enhanced_prompt += page_objects_info
        enhanced_prompt += "\nUse these page objects and their available selectors and methods in your test script to implement the test case steps and assertions."
        
    except Exception as e:
        # If there's an error extracting page object info, just use the basic prompt
        print(format_console_output("warning", f"Error extracting page object info: {str(e)}"))
        enhanced_prompt = template.format(
            test_case_id=test_case_id,
            test_case_title=test_case_title,
            test_case_steps=test_case_steps,
            test_case_expected_results=test_case_expected_results,
            page_objects=page_objects_text
        )
    
    # Send to AI
    print(format_console_output("info", f"Generating test script for: {test_case_id}"))
    
    try:
        response = await TestCaseAgent.a_generate_reply(
            messages=[{"role": "user", "content": enhanced_prompt}]
        )
        
        # Parse the response
        import re
        
        # Extract code block if present, otherwise use the whole response
        code_match = re.search(r'```(?:javascript)?\s*([\s\S]*?)\s*```', response)
        if code_match:
            script_content = code_match.group(1).strip()
        else:
            script_content = response.strip()
        
        print(format_console_output("success", f"Successfully generated script for {test_case_id}"))
        return script_content
        
    except Exception as e:
        print(format_console_output("error", f"Error generating script: {str(e)}"))
        return generate_fallback_script(test_case, page_objects)



async def generate_test_script(test_case, page_objects, feature_data):
    """
    Generate a Playwright test script using AI.
    
    Args:
        test_case (dict): The test case to generate a script for
        page_objects (list): List of available page objects
        feature_data (dict): The feature data
        
    Returns:
        str: The generated test script content
    """
    from config.config import TestCaseAgent
    
    # Get the prompt template
    template = _load_prompt_template("test_script.txt")
    
    # Extract test case information
    test_case_id = test_case.get('id', 'unknown')
    test_case_title = test_case.get('title', 'Unknown Test Case')
    test_case_steps = test_case.get('steps', 'No steps available')
    test_case_expected_results = test_case.get('expectedResults', 'No expected results available')
    
    # Format the page objects list
    page_objects_text = ", ".join(page_objects)
    
    # Format the prompt
    prompt = template.format(
        test_case_id=test_case_id,
        test_case_title=test_case_title,
        test_case_steps=test_case_steps,
        test_case_expected_results=test_case_expected_results,
        page_objects=page_objects_text
    )
    
    # Send to AI
    print(format_console_output("info", f"Generating test script for: {test_case_id}"))
    
    try:
        response = await TestCaseAgent.a_generate_reply(
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the response
        import re
        
        # Extract code block if present, otherwise use the whole response
        code_match = re.search(r'```(?:javascript)?\s*([\s\S]*?)\s*```', response)
        if code_match:
            script_content = code_match.group(1).strip()
        else:
            script_content = response.strip()
        
        print(format_console_output("success", f"Successfully generated script for {test_case_id}"))
        return script_content
        
    except Exception as e:
        print(format_console_output("error", f"Error generating script: {str(e)}"))
        return generate_fallback_script(test_case, page_objects)


def generate_fallback_script(test_case, page_objects):
    """
    Generate a basic fallback script if AI generation fails.
    
    Args:
        test_case (dict): The test case data
        page_objects (list): List of available page objects
        
    Returns:
        str: A basic script implementation
    """
    test_id = test_case.get('id', 'unknown')
    title = test_case.get('title', 'Unknown Test Case')
    steps = test_case.get('steps', 'No steps available')
    expected = test_case.get('expectedResults', 'No expected results available')
    
    # Determine which page object to use - prefer something specific over BasePage
    primary_page = "BasePage"
    for page in page_objects:
        if page != "BasePage":
            primary_page = page
            break
    
    return f"""// {test_id}: {title}
const {{ test, expect }} = require('@playwright/test');
const {{ {primary_page} }} = require('../pages/{primary_page}');

/**
 * Test case for: {title}
 * This is a fallback implementation because AI generation failed.
 */
test('{title}', async ({{ page }}) => {{
  // Initialize page objects
  const pageObj = new {primary_page}(page);
  
  // Navigate to starting page
  await pageObj.navigateTo();
  
  // TODO: Implement test steps
  // Steps:
  /*
{steps}
  */
  
  // TODO: Implement assertions
  // Expected Results:
  /*
{expected}
  */
  
  // Basic assertions
  await expect(page).toHaveTitle(/.*/)
  
  // This is a fallback implementation - needs manual completion
  console.log('Test {test_id} needs manual implementation');
}});
"""