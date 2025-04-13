# dev_enhance.py
import os
import sys
import json
import asyncio
from orchestrator.agent_orchestrator import PlaywrightAgentOrchestrator

async def enhance_from_existing_selectors(test_case_id, selectors_file=None):
    """
    Enhance Playwright test directly from existing selectors file.
    
    Args:
        test_case_id (str): Test case ID
        selectors_file (str): Path to selectors JSON file (optional)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use provided selectors file or default based on test case ID
        if not selectors_file:
            selectors_file = f"{test_case_id}_selectors.json"
        
        # Check if selectors file exists
        if not os.path.exists(selectors_file):
            print(f"❌ Selectors file not found: {selectors_file}")
            return False
        
        # Load selectors
        with open(selectors_file, "r", encoding="utf-8") as f:
            selectors = json.load(f)
        
        # Create a minimal test case object
        test_case = {
            "id": test_case_id,
            "title": f"Test Case {test_case_id}",
            "steps": "Steps for test case",
            "expectedResults": "Expected results for test case"
        }
        
        # Initialize orchestrator
        orchestrator = PlaywrightAgentOrchestrator(output_dir="playwright_tests")
        
        # Generate Page Object Models from selectors
        # The generate_from_selectors method automatically uses specialized agents if available
        success = await orchestrator.generate_from_selectors(test_case_id, test_case, selectors)
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python dev_enhance.py <TEST_CASE_ID> [selectors_file]")
        return
    
    test_case_id = sys.argv[1]
    selectors_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = await enhance_from_existing_selectors(test_case_id, selectors_file)
    
    if success:
        print(f"✅ Successfully enhanced Playwright test for {test_case_id}")
    else:
        print(f"❌ Failed to enhance Playwright test for {test_case_id}")

if __name__ == "__main__":
    asyncio.run(main())