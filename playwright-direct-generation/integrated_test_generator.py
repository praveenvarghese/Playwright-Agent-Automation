import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from browser_use import Browser, BrowserConfig, Agent
from langchain_openai import AzureChatOpenAI
from vector_retrieval import fetch_test_case_by_id

async def generate_integrated_test(test_case_id: str):
    """
    Integrated test generator that:
    1. Retrieves test case details 
    2. Runs browser automation 
    3. Extracts selectors
    4. Generates Playwright test script
    All in one command.
    """
    # Load environment variables
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(dotenv_path)

    # Get environment variables
    app_url = os.getenv("APP_URL")
    username = os.getenv("APP_USERNAME")
    password = os.getenv("APP_PASSWORD")
    headless = os.getenv("APP_HEADLESS", "true").lower() in ["true", "1", "yes"]

    # Step 1: Fetch test case information
    print(f"\n📥 Fetching test case '{test_case_id}'...")
    test_case = await fetch_test_case_by_id(test_case_id)
    if not test_case:
        print("❌ Test case not found.")
        return
    print(f"✅ Test case found: {test_case.get('title', 'Unknown')}")

    # Step 2: Initialize LLM and Browser
    llm = AzureChatOpenAI(
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    browser = Browser(config=BrowserConfig(headless=headless))

    # Step 3: Run the browser automation
    print("🔍 Step 1: Exploring UI and collecting element information...")
    ui_agent = Agent(
        task=f"""
        You are a Playwright automation engineer using browser_use.

        Your task:
        1. Go to "https://praveen-2.aimms.cloud/v3/users/" and log in using:
           - Username: {username}
           - Password: {password}

        2. Perform this test case exactly:
        Title: {test_case['title']}
        Steps:
        {test_case['steps']}

        Expected Results:
        {test_case['expectedResults']}

        For each element you interact with, determine the most optimal selector:
        - Prefer ID-based selectors when available (#id)
        - Use attribute combinations for form elements (input[name="x"][type="y"])
        - Use distinctive class names for other elements (button.distinctive-class)

        Log each interaction clearly so the system can extract selectors later..
        """,
        browser=browser,
        llm=llm
    )

    try:
        # Run the browser automation
        result = await ui_agent.run()

        # Save the raw result
        with open(f"{test_case_id}_raw_agent_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        with open(f"{test_case_id}_raw_agent_result.json", "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        # Step 4: Extract selectors from the result
        print("🔍 Extracting selectors from raw agent outputs...")
        selectors = extract_selectors(json.loads(result.model_dump_json()), test_case_id)

        # Step 5: Generate Playwright test from the selectors
        print("🔧 Generating Playwright test script...")
        generate_playwright_test(test_case_id, test_case, selectors, app_url, username, password)

        print(f"✅ Playwright test script generated: {test_case_id}.spec.js")

    except Exception as e:
        print(f"❌ Error during generation: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()


def extract_selectors(result, test_case_id):
    """Extract selectors and actions from the browser automation result."""
    seen = set()
    selector_list = []
    selector_text = "# CSS selectors detected by browser_use\n\n"

    # Add debug logging
    print(f"Result structure: {type(result)}")
    print(f"Keys in result: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
    
    history_items = result.get("history", []) if isinstance(result, dict) else []
    print(f"Number of history items: {len(history_items)}")
    
    for i, history_item in enumerate(history_items):
        print(f"Processing history item {i+1}/{len(history_items)}")
        
        actions = history_item.get("result", []) if isinstance(history_item, dict) else []
        elements = history_item.get("state", {}).get("interacted_element", []) if isinstance(history_item, dict) else []
        
        print(f"  Actions: {len(actions)}, Elements: {len(elements)}")
        
        for j, (action, element) in enumerate(zip(actions, elements)):
            try:
                if not element or not isinstance(element, dict) or "css_selector" not in element:
                    print(f"  Skipping item {j+1} - no valid element or selector")
                    continue

                selector = element["css_selector"]
                if selector in seen:
                    print(f"  Skipping duplicate selector: {selector[:30]}...")
                    continue
                seen.add(selector)

                tag = element.get("tag_name", "unknown")
                
                # Safely handle extracted_content
                extracted_content = action.get("extracted_content") if isinstance(action, dict) else None
                content = "" if extracted_content is None else str(extracted_content).lower()

                # Determine action type
                action_type = "unknown"
                if "click" in content:
                    action_type = "click"
                elif "input" in content:
                    action_type = "input"
                elif "scroll" in content:
                    action_type = "scroll"
                
                print(f"  Found {action_type} action on {tag} element")

                selector_list.append({
                    "action": action_type,
                    "tag": tag,
                    "text": content,
                    "selector": selector
                })

                selector_text += f"Action: {action_type}\nElement: {tag}\nText: {content}\nSelector: {selector}\n\n"
            except Exception as e:
                print(f"  Error processing action/element {j+1}: {str(e)}")
                continue

    # Save the selectors to files
    with open(f"{test_case_id}_selectors.json", "w", encoding="utf-8") as f:
        json.dump(selector_list, f, indent=2)
    with open(f"{test_case_id}_selectors.txt", "w", encoding="utf-8") as f:
        f.write(selector_text)

    print(f"✅ Extracted {len(selector_list)} selectors with actions")
    return selector_list

def extract_input_value(text):
    """Extract the actual input value from the text description."""
    if "input" in text:
        # Format is typically "⌨️ input VALUE into index N"
        parts = text.split("input ", 1)
        if len(parts) > 1:
            value_parts = parts[1].split(" into ", 1)
            if value_parts:
                return value_parts[0].strip()
    return ""


def generate_playwright_test(test_case_id, test_case, selectors, app_url, username, password):
    """Generate a Playwright test file from the extracted selectors."""
    test_title = test_case.get('title', f'Test Case {test_case_id}')
    # Escape single quotes in test title for JavaScript
    test_title = test_title.replace("'", "\\'")
    
    expected_results = test_case.get('expectedResults', 'Test completes successfully')
    # Escape single quotes in expected results for JavaScript
    expected_results = expected_results.replace("'", "\\'")
    # Clean up line breaks and extraneous characters
    expected_results = expected_results.replace('\n', ' ').replace('---', '').strip()
    
    # Start building the test script
    test_script = f"""// Playwright test for {test_case_id}: {test_title}
// Generated automatically from selectors

const {{ test, expect }} = require('@playwright/test');

test('{test_title}', async ({{ page }}) => {{
  // Navigate to application
  await page.goto('{app_url}');

  // Perform test steps
"""

    # Add each test step based on the selectors
    for i, selector in enumerate(selectors):
        action = selector['action']
        # Escape single quotes in CSS selector for JavaScript
        selector_css = selector['selector'].replace("'", "\\'")
        
        if action == 'input':
            # Extract the input value from the text
            input_value = extract_input_value(selector['text'])
            # Escape single quotes in input value for JavaScript
            input_value = input_value.replace("'", "\\'")
            
            test_script += f"""
  // Step {i+1}: Input "{input_value}" into {selector['tag']}
  await page.fill('{selector_css}', '{input_value}');
"""
        elif action == 'click':
            # Extract button name if available
            button_text = ''
            if 'index' in selector['text'] and ':' in selector['text']:
                button_text = selector['text'].split(':', 1)[1].strip()
                # Clean up any line breaks in button text
                button_text = button_text.replace('\n', ' ').strip()
                # Escape single quotes in button text for JavaScript
                button_text = button_text.replace("'", "\\'")
            
            test_script += f"""
  // Step {i+1}: Click {selector['tag']}{' "' + button_text + '"' if button_text else ''}
  await page.click('{selector_css}');
"""
        elif action == 'scroll':
            test_script += f"""
  // Step {i+1}: Scroll to element
  await page.focus('{selector_css}');
"""

    # Add verification based on expected results
    test_script += f"""
  // Verification
  await page.waitForLoadState('networkidle');
  
  // Add assertions based on expected results
  await expect(page.locator('text=test environment')).toBeVisible();
  await expect(page.locator('text=Native')).toBeVisible();
}});
"""

    # Write the test script to a file
    with open(f"{test_case_id}.spec.js", "w", encoding="utf-8") as f:
        f.write(test_script)
    
    return test_script

async def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("⚠️ Usage: python integrated_test_generator.py <TEST_CASE_ID>")
        return
    
    test_case_id = sys.argv[1]
    await generate_integrated_test(test_case_id)


if __name__ == '__main__':
    asyncio.run(main())