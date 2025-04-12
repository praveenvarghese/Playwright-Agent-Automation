"""
Integration module to connect AI-enhanced Playwright generation with the existing system.
"""

import os
import json
from agent_orchestrator import PlaywrightAgentOrchestrator

def enhance_playwright_script(test_case_id, original_script_path, selectors_file_path, output_dir="playwright_tests"):
    """
    Enhance an existing Playwright script using AI agents.
    This function integrates with the existing generation system.
    
    Args:
        test_case_id (str): Test case ID
        original_script_path (str): Path to the original Playwright script
        selectors_file_path (str): Path to the selectors JSON file
        output_dir (str): Directory to save enhanced files
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load original script
        if not os.path.exists(original_script_path):
            print(f"❌ Original script not found: {original_script_path}")
            return False
            
        with open(original_script_path, "r", encoding="utf-8") as f:
            original_script = f.read()
            
        # Load selectors data
        if not os.path.exists(selectors_file_path):
            print(f"❌ Selectors file not found: {selectors_file_path}")
            return False
            
        with open(selectors_file_path, "r", encoding="utf-8") as f:
            selectors_data = json.load(f)
            
        # Initialize orchestrator
        orchestrator = PlaywrightAgentOrchestrator(output_dir=output_dir)
        
        # Enhance the test
        success = orchestrator.enhance_test(test_case_id, original_script, selectors_data)
        
        return success
        
    except Exception as e:
        print(f"❌ Error enhancing Playwright script: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def generate_and_enhance(test_case_id):
    """
    Generate a basic Playwright script and then enhance it.
    This function integrates with the existing integrated_test_generator.
    
    Args:
        test_case_id (str): Test case ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Import the integrated test generator dynamically
        # This assumes it's in the parent directory
        import sys
        import os
        
        # Add parent directory to path
        parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        sys.path.append(parent_dir)
        
        # Import the integrated_test_generator module
        from integrated_test_generator import generate_integrated_test
        import asyncio
        
        # Run the integrated test generator to create basic script
        print(f"🚀 Generating basic Playwright script for {test_case_id}")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(generate_integrated_test(test_case_id))
        
        # Check if files were generated
        original_script_path = f"{test_case_id}.spec.js"
        selectors_file_path = f"{test_case_id}_selectors.json"
        
        if not os.path.exists(original_script_path) or not os.path.exists(selectors_file_path):
            print(f"❌ Basic script generation failed")
            return False
            
        # Enhance the generated script
        print(f"🚀 Enhancing Playwright script for {test_case_id}")
        success = enhance_playwright_script(
            test_case_id=test_case_id,
            original_script_path=original_script_path,
            selectors_file_path=selectors_file_path,
            output_dir="enhanced_playwright_tests"
        )
        
        return success
        
    except Exception as e:
        print(f"❌ Error in generate_and_enhance: {str(e)}")
        import traceback
        traceback.print_exc()
        return False