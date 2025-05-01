#!/usr/bin/env python3
"""
Standalone test generator that combines browser automation and Playwright test generation.
This script doesn't depend on dev_enhance.py or enhance_playwright_tests.py.
"""

import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from browser_use import Browser, BrowserConfig, Agent
from langchain_openai import AzureChatOpenAI
from vector_retrieval import fetch_test_case_by_id
from agent_config import create_agents
from orchestrator.agent_orchestrator import PlaywrightAgentOrchestrator
from testcase_utils import extract_test_case_from_selectors

async def generate_test(test_case_id: str, output_dir: str = "playwright_tests", use_design_first: bool = True):
    """
    End-to-end test generation workflow that combines browser automation and Playwright generation.
    
    Args:
        test_case_id (str): Test case ID (e.g., "TC-ENV-001")
        output_dir (str): Output directory for generated tests
        use_design_first (bool): Whether to use the design-first approach
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"\n🚀 Starting test generation for {test_case_id}")
        
        # Step 1: Fetch test case information
        print(f"\n📚 Step 1: Fetching test case data")
        test_case = await fetch_test_case_by_id(test_case_id)
        if not test_case:
            print(f"❌ Test case not found: {test_case_id}")
            return False
            
        print(f"✅ Test case found: {test_case.get('title', 'Unknown')}")
        
        # Step 2: Run browser automation to generate selectors
        print(f"\n🔍 Step 2: Running browser automation to generate selectors")
        selectors = await run_browser_automation(test_case_id, test_case)
        if not selectors:
            print(f"❌ Failed to generate selectors")
            return False
            
        selector_file = f"{test_case_id}_selectors.json"
        print(f"✅ Generated {len(selectors)} selectors and saved to {selector_file}")

        extracted_values = extract_test_case_from_selectors(selectors)
        test_case.update(extracted_values)
        # Step 3: Generate Playwright tests with Page Object Models
        print(f"\n🎭 Step 3: Generating Playwright tests with Page Object Models")
        success = await generate_playwright_tests(test_case_id, test_case, selectors, output_dir, use_design_first)
        
        if success:
            print(f"✅ Playwright tests generated successfully in {output_dir}")
        else:
            print(f"❌ Failed to generate Playwright tests")
            return False
            
        print(f"\n🎉 Test generation completed successfully for {test_case_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error in test generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def run_browser_automation(test_case_id: str, test_case: dict):
    """
    Run browser automation to generate selectors.
    
    Args:
        test_case_id (str): Test case ID
        test_case (dict): Test case data
        
    Returns:
        list: Generated selectors or None if failed
    """
    try:
        # Get environment variables
        app_url = os.getenv("APP_URL")
        username = os.getenv("APP_USERNAME")
        password = os.getenv("APP_PASSWORD")
        headless = os.getenv("APP_HEADLESS", "true").lower() in ["true", "1", "yes"]
        
        # Initialize LLM and Browser
        llm = AzureChatOpenAI(
            openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )
        browser = Browser(config=BrowserConfig(headless=headless))
        
        # Create the Agent with the task
        ui_agent = Agent(
            task=f"""
            You are a Playwright automation engineer using browser_use.

            Your task:
            1. Go to "{app_url}" and log in using:
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

            Log each interaction clearly so the system can extract selectors later.
            """,
            browser=browser,
            llm=llm
        )
        
        # Run the browser automation
        result = await ui_agent.run()
        
        # Save the raw result
        with open(f"{test_case_id}_raw_agent_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        with open(f"{test_case_id}_raw_agent_result.json", "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
            
        # Extract selectors from the result
        selectors = extract_selectors(json.loads(result.model_dump_json()), test_case_id)
        
        await browser.close()
        return selectors
        
    except Exception as e:
        print(f"❌ Error in browser automation: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def extract_selectors(result, test_case_id):
    """
    Extract selectors from browser automation result.
    Based on the original extraction function from integrated_test_generator.py.
    
    Args:
        result (dict): Browser automation result
        test_case_id (str): Test case ID
        
    Returns:
        list: Extracted selectors
    """
    seen = set()
    selector_list = []
    selector_text = "# CSS selectors detected by browser_use\n\n"

    # Process history items
    history_items = result.get("history", []) if isinstance(result, dict) else []
    print(f"Number of history items: {len(history_items)}")
    
    for i, history_item in enumerate(history_items):
        print(f"Processing history item {i+1}/{len(history_items)}")
        
        actions = history_item.get("result", []) if isinstance(history_item, dict) else []
        elements = history_item.get("state", {}).get("interacted_element", []) if isinstance(history_item, dict) else []
        
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

async def generate_playwright_tests(test_case_id, test_case, selectors, output_dir, use_design_first):
    """
    Generate Playwright tests with Page Object Models using the orchestrator.
    
    Args:
        test_case_id (str): Test case ID
        test_case (dict): Test case data
        selectors (list): List of selectors
        output_dir (str): Output directory
        use_design_first (bool): Whether to use design-first approach
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize orchestrator with the specified output directory
        orchestrator = PlaywrightAgentOrchestrator(output_dir=output_dir)
        
        # Use the design-first approach or original approach based on parameter
        if use_design_first:
            print("Using design-first approach for Playwright generation")
            success = orchestrator.generate_with_design_first(test_case_id, test_case, selectors)
        else:
            print("Using original approach for Playwright generation")
            success = await orchestrator.generate_from_selectors(test_case_id, test_case, selectors)
            
        return success
        
    except Exception as e:
        print(f"❌ Error generating Playwright tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def setup_environment():
    """Set up environment and load required variables."""
    # Add directory to path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(script_dir)
    
    # Load environment variables
    load_dotenv()
    
    # Check for required environment variables
    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "APP_URL",
        "APP_USERNAME",
        "APP_PASSWORD"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        sys.exit(1)

async def main():
    """Main entry point for the script."""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate complete Playwright tests with browser automation")
    
    parser.add_argument(
        "test_case_id",
        help="Test case ID (e.g., TC-ENV-001)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="playwright_tests",
        help="Output directory for generated tests (default: playwright_tests)"
    )
    
    parser.add_argument(
        "--skip-design",
        action="store_true",
        help="Skip the design-first approach for Playwright generation"
    )
    
    args = parser.parse_args()
    
    # Setup environment
    setup_environment()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run the test generation
    success = await generate_test(
        test_case_id=args.test_case_id,
        output_dir=args.output_dir,
        use_design_first=not args.skip_design
    )
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())