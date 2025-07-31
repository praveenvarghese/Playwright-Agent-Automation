#!/usr/bin/env python3
"""
DEBUG VERSION - Simple Complete Generator 
Adds extensive debugging to show why selectors aren't being extracted
"""

import asyncio
import sys
import os
import json

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import existing functions
from playwright_generation.runners.mcp_test_generator import (
    fetch_test_case,
    run_mcp_automation, 
    extract_selectors
)
from playwright_generation.runners.pom_test_runner import (
    create_pom_test_workflow,
    save_page_objects,
    save_test_script
)

def debug_execution_log(execution_log, test_case_id):
    """Debug function to analyze execution log structure"""
    print("\n🔍 DEBUG: Analyzing execution log...")
    print(f"📊 Execution log type: {type(execution_log)}")
    print(f"📊 Execution log length: {len(execution_log) if execution_log else 0}")
    
    if not execution_log:
        print("❌ DEBUG: Execution log is empty!")
        return
    
    # Save detailed debug info
    debug_file = f"debug_{test_case_id}_execution_analysis.json"
    with open(debug_file, "w") as f:
        json.dump({
            "log_length": len(execution_log),
            "log_type": str(type(execution_log)),
            "log_structure": execution_log[:3] if len(execution_log) > 0 else [],  # First 3 entries
            "all_tools_used": [entry.get("tool", "unknown") for entry in execution_log] if isinstance(execution_log, list) else "not_a_list"
        }, f, indent=2)
    
    print(f"📁 Saved execution log analysis to: {debug_file}")
    
    # Analyze each entry
    for i, entry in enumerate(execution_log[:5]):  # Look at first 5 entries
        print(f"\n--- Entry {i} ---")
        print(f"Tool: {entry.get('tool', 'MISSING')}")
        print(f"Args keys: {list(entry.get('args', {}).keys())}")
        print(f"Result keys: {list(entry.get('result', {}).keys())}")
        
        # Look for Playwright code specifically
        result = entry.get("result", {})
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list):
                for content_item in content:
                    if isinstance(content_item, dict) and "text" in content_item:
                        text = content_item["text"]
                        if "await page." in text:
                            print(f"✅ Found Playwright code in entry {i}")
                            print(f"Sample: {text[:100]}...")
                        else:
                            print(f"⚠️ Entry {i} has text but no 'await page.'")

def debug_selector_extraction(execution_log, test_case_id):
    """Debug the selector extraction process step by step"""
    print("\n🔍 DEBUG: Stepping through selector extraction...")
    
    selectors = []
    
    for i, entry in enumerate(execution_log):
        print(f"\n--- Processing Entry {i} ---")
        tool = entry.get("tool", "unknown")
        args = entry.get("args", {})
        result = entry.get("result", {})
        
        print(f"Tool: {tool}")
        print(f"Args: {args}")
        
        if tool == "browser_navigate":
            selector_entry = {
                "action": "navigate", 
                "url": args.get('url', '')
            }
            selectors.append(selector_entry)
            print(f"✅ Added navigate selector: {selector_entry}")
            
        elif tool in ["browser_type", "browser_click"]:
            print(f"🔍 Processing {tool} tool...")
            
            # Try to extract playwright code
            from playwright_generation.runners.mcp_test_generator import extract_playwright_code
            playwright_code = extract_playwright_code(result)
            
            if playwright_code:
                print(f"✅ Extracted Playwright code: {playwright_code}")
                
                # Try LLM parsing
                from playwright_generation.runners.mcp_test_generator import llm_parse_action
                try:
                    parsed_action = llm_parse_action(tool, playwright_code, args)
                    if parsed_action:
                        selectors.append(parsed_action)
                        print(f"✅ LLM parsed successfully: {parsed_action}")
                    else:
                        print("❌ LLM parsing returned None")
                        # Fallback
                        fallback_selector = {
                            "action": "input" if tool == "browser_type" else "click",
                            "rawSelector": playwright_code,
                            "elementName": args.get("element", ""),
                            "value": args.get("text", "") if tool == "browser_type" else None
                        }
                        selectors.append(fallback_selector)
                        print(f"⚠️ Used fallback selector: {fallback_selector}")
                except Exception as e:
                    print(f"❌ LLM parsing failed: {str(e)}")
                    
            else:
                print(f"❌ No Playwright code found in result: {result}")
        else:
            print(f"⚠️ Skipping tool: {tool}")
    
    # Save debug selectors
    debug_selectors_file = f"debug_{test_case_id}_extracted_selectors.json"
    with open(debug_selectors_file, "w") as f:
        json.dump(selectors, f, indent=2)
    
    print(f"\n📊 DEBUG SUMMARY:")
    print(f"Total selectors extracted: {len(selectors)}")
    print(f"📁 Debug selectors saved to: {debug_selectors_file}")
    
    return selectors

async def generate_complete_test_reusing_functions(test_case_id: str, output_dir: str = "complete_tests"):
    """
    DEBUG VERSION: Complete test generation with extensive debugging
    """
    
    print(f"🚀 DEBUG Complete Test Generation for {test_case_id}")
    
    # Step 1: Fetch test case
    print("📚 Step 1: Fetching test case...")
    test_case = await fetch_test_case(test_case_id)
    if not test_case:
        print("❌ Failed to fetch test case")
        return False
    print("✅ Test case fetched successfully")
    
    # Step 2: Run MCP automation
    print("🎭 Step 2: Running MCP automation...")
    execution_log = await run_mcp_automation(test_case_id, test_case)
    if not execution_log:
        print("❌ MCP automation failed")
        return False
    print("✅ MCP automation completed")
    
    # DEBUG: Analyze execution log
    debug_execution_log(execution_log, test_case_id)
    
    # Step 3: Extract selectors with debugging
    print("🔍 Step 3: Extracting selectors with DEBUG...")
    
    # First try original function
    selectors = extract_selectors(execution_log)
    print(f"Original extract_selectors() returned: {len(selectors) if selectors else 0} selectors")
    
    # Then try debug version
    debug_selectors = debug_selector_extraction(execution_log, test_case_id)
    print(f"Debug extraction returned: {len(debug_selectors)} selectors")
    
    # Use debug version if original failed
    if not selectors and debug_selectors:
        print("⚠️ Using debug-extracted selectors since original failed")
        selectors = debug_selectors
    
    if not selectors:
        print("❌ No selectors extracted by either method!")
        print("Check the debug files to see what went wrong:")
        print(f"  - debug_{test_case_id}_execution_analysis.json")
        print(f"  - debug_{test_case_id}_extracted_selectors.json")
        return False
    
    # Save selectors to JSON file
    selectors_file = f"{test_case_id}_selectors.json"
    with open(selectors_file, "w") as f:
        json.dump(selectors, f, indent=2)
    print(f"✅ Generated {len(selectors)} selectors")
    print(f"📁 Saved selectors to: {selectors_file}")
    
    # Step 4: Run 6-step workflow
    print("⚙️ Step 4: Running 6-step generation workflow...")
    success = await run_6_step_workflow_reused(test_case_id, test_case, selectors, output_dir)
    
    if success:
        print(f"🎉 Complete generation successful!")
        print(f"📁 Files saved in {output_dir}")
        print(f"📁 Selectors saved in {selectors_file}")
    
    return success

async def run_6_step_workflow_reused(test_case_id, test_case, selectors, output_dir):
    """Run 6-step workflow using existing workflow from pom_test_runner.py"""
    
    try:
        # Create workflow (reuse from pom_test_runner.py)
        workflow = create_pom_test_workflow()
        
        # Initial state (same as pom_test_runner.py)
        initial_state = {
            "test_case_id": test_case_id,
            "test_case": test_case,
            "selectors": selectors,
            "messages": [],
            "pom_response": "",
            "pom_critique": "",
            "improved_pom": "",
            "test_script": "",
            "test_critique": "",
            "final_test_script": "",
            "integration_feedback": "",
            "integration_improvements": "",
            "integration_final_check": "",
            "integration_iteration": 0,
            "needs_integration_improvement": False,
            "page_objects": [],
            "test_file": ""
        }
        
        # Run workflow
        print("▶️ Running 6-step workflow...")
        final_state = workflow.invoke(initial_state)
        
        # Save conversation history
        conversation_file = f"debug_{test_case_id}_complete_conversation.json"
        with open(conversation_file, "w", encoding="utf-8") as f:
            messages_data = []
            for msg in final_state["messages"]:
                messages_data.append({
                    "type": msg.__class__.__name__,
                    "content": msg.content,
                    "name": getattr(msg, 'name', 'unknown'),
                    "additional_kwargs": getattr(msg, 'additional_kwargs', {})
                })
            json.dump(messages_data, f, indent=2)
        
        print(f"📝 Saved conversation history to {conversation_file}")
        
        # Extract and save results
        page_objects = final_state["page_objects"]
        test_file = final_state["test_file"]
        
        # Create output directories
        pages_dir = os.path.join(output_dir, "pages")
        tests_dir = os.path.join(output_dir, "tests")
        
        if page_objects:
            saved_page_files = save_page_objects(page_objects, pages_dir)
            print(f"✅ Generated {len(saved_page_files)} page object files")
        else:
            print("⚠️ No page objects found")
        
        if test_file:
            saved_test_file = save_test_script(test_file, tests_dir, test_case_id)
            print(f"✅ Generated test file: {saved_test_file}")
        else:
            print("⚠️ No test file found")
        
        return page_objects and test_file
        
    except Exception as e:
        print(f"❌ Error in 6-step workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def setup_environment():
    """Validate environment variables"""
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", 
        "AZURE_OPENAI_DEPLOYMENT_NAME", "APP_URL", "APP_USERNAME", "APP_PASSWORD"
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python debug_mcp_test_generator_simple.py <TEST_CASE_ID> [output_dir]")
        print("Example: python debug_mcp_test_generator_simple.py TC-ENV-001")
        return
        
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "complete_tests"
    
    setup_environment()
    
    success = await generate_complete_test_reusing_functions(test_case_id, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())