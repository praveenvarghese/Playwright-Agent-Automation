#!/usr/bin/env python3
"""
Simple Complete Generator - Reuses existing functions
Combines: MCP execution (from mcp_test_generator.py) + 6-step workflow (from pom_test_runner.py)
"""

import asyncio
import sys
import os

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

async def generate_complete_test_reusing_functions(test_case_id: str, output_dir: str = "complete_tests"):
    """
    Complete test generation reusing existing functions
    
    Flow:
    1. Fetch test case (reuse from mcp_test_generator.py)
    2. Run MCP automation (reuse from mcp_test_generator.py) 
    3. Extract selectors (reuse from mcp_test_generator.py)
    4. Run 6-step workflow (reuse from pom_test_runner.py)
    5. Save results (reuse from pom_test_runner.py)
    """
    
    print(f"🚀 Complete Test Generation for {test_case_id} (reusing existing functions)")
    
    # Step 1: Fetch test case (reuse existing function)
    print("📚 Step 1: Fetching test case...")
    test_case = await fetch_test_case(test_case_id)
    if not test_case:
        return False
    
    # Step 2: Run MCP automation (reuse existing function)
    print("🎭 Step 2: Running MCP automation...")
    execution_log = await run_mcp_automation(test_case_id, test_case)
    if not execution_log:
        return False
    
    # Step 3: Extract selectors (reuse existing function)
    print("🔍 Step 3: Extracting selectors...")
    selectors = extract_selectors(execution_log)
    if not selectors:
        print("❌ No selectors extracted")
        return False
    
    print(f"✅ Extracted {len(selectors)} selectors")
    
    # Step 4: Run 6-step workflow (reuse existing workflow)
    print("⚙️ Step 4: Running 6-step generation workflow...")
    success = await run_6_step_workflow_reused(test_case_id, test_case, selectors, output_dir)
    
    if success:
        print(f"🎉 Complete generation successful!")
        print(f"📁 Files saved in {output_dir}")
    
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
        
        # Run workflow (same as pom_test_runner.py)
        print("▶️ Running 6-step workflow...")
        final_state = workflow.invoke(initial_state)
        
        # Save conversation history (same as pom_test_runner.py)
        conversation_file = f"debug_{test_case_id}_complete_conversation.json"
        import json
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
        
        # Extract and save results (reuse existing save functions)
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
        print("Usage: python simple_complete_generator.py <TEST_CASE_ID> [output_dir]")
        print("Example: python simple_complete_generator.py TC-ENV-001")
        return
        
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "complete_tests"
    
    setup_environment()
    
    success = await generate_complete_test_reusing_functions(test_case_id, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())