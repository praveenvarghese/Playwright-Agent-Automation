#!/usr/bin/env python3
"""
Playwright Test Generator - Main Entry Point
Refactored for better maintainability with JSON validation
"""

import asyncio
import os
import sys
import re
import warnings
from typing import TypedDict, List
from dotenv import load_dotenv

# Suppress warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed transport.*")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

# Add project to path  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import refactored modules
from common.test_case_fetcher import fetch_test_case
from mcp_helpers.automation_runner import run_mcp_automation
from orchestration.workflow_builder import create_pom_test_workflow
from orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized
from common.validation_helpers import setup_environment, check_dependencies
from common.file_utils import save_page_objects, save_test_script

# =============================================================================
# MAIN EXECUTION FUNCTIONS
# =============================================================================

async def generate_complete_test(test_case_id: str, output_dir: str = "complete_tests"):
    """Complete test generation workflow with validation"""
    
    print(f"🚀 Generating complete test with validation for {test_case_id}")
    
    # Step 1: Get test case from configured source with validation
    print("📚 Fetching and validating test case...")
    test_case = await fetch_test_case(test_case_id)
    if not test_case:
        print("❌ Test case not found or validation failed")
        return False
    print(f"✅ Found and validated: {test_case.get('title', 'Unknown')}")
    test_case_id = test_case['id']
    
    # Show structured steps info
    structured_steps = test_case.get('structured_steps', [])
    if structured_steps:
        steps_with_expected = [s for s in structured_steps if s.get('expected')]
        print(f"📋 Found {len(structured_steps)} total steps, {len(steps_with_expected)} with expected results")
    
    # Step 2: Run MCP automation with conditional verification
    print("🎭 Running MCP automation with conditional verification...")
    execution_log = await run_mcp_automation(test_case_id, test_case)
    if not execution_log:
        print("❌ MCP automation failed")
        return False
    print("✅ MCP automation completed with verification data")
        
    #Step 3: Run 6-step POM/Test generation workflow with validation
    # print("⚙️ Running enhanced 6-step generation workflow with validation...")
    # success = await run_workflow(test_case_id, test_case, output_dir)
    
    # if success:
    #     print(f"🎉 Complete test generation successful with validation!")
    #     print(f"📁 Files saved in {output_dir}")
    # else:
    #     print("❌ Workflow failed")
    
    # return success

async def run_workflow(test_case_id, test_case, output_dir):
    """Run the enhanced 6-step generation workflow (UPDATED: cleaned up)"""
    
    try:
        workflow = create_pom_test_workflow()
        
        initial_state = {
            "test_case_id": test_case_id,
            "test_case": test_case,
            "messages": [],
            "page_objects": [],
            "test_file": ""
        }
        
        print("▶️ Running enhanced 6-step workflow with validation...")
        final_state = workflow.invoke(initial_state)
        
        # UPDATED: Simplified extraction - no fallbacks needed
        page_objects = final_state.get("page_objects", [])
        test_file = final_state.get("test_file", "")
        
        # Save results
        pages_dir = os.path.join(output_dir, "pages")
        tests_dir = os.path.join(output_dir, "tests")
        
        if page_objects:
            save_page_objects(page_objects, pages_dir)
            print(f"✅ Generated {len(page_objects)} page object files")
        
        if test_file:
            save_test_script(test_file, tests_dir, test_case_id)
            print(f"✅ Generated test file with method validation")
        
        return bool(page_objects and test_file)
        
    except Exception as e:
        print(f"❌ Workflow error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main entry point (UPDATED: cleaned up validation)"""
    if len(sys.argv) < 2:
        print("Usage: python mcp_test_generator_simple.py <TEST_CASE_ID> [output_dir]")
        print("Example: python mcp_test_generator_simple.py TC-ENV-001")
        print("Example: python mcp_test_generator_simple.py TestCaseFile.txt")
        print("Example: python mcp_test_generator_simple.py 12345  # Azure DevOps work item")
        return
        
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "complete_tests"
    
    # UPDATED: Use renamed function
    if not check_dependencies():
        sys.exit(1)
    
    setup_environment()
    
    success = await generate_complete_test(test_case_id, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())