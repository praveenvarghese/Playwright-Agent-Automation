#!/usr/bin/env python3
"""
Unit test for testing PlaywrightAgentOrchestrator with existing selector files.
"""

import asyncio
import json
import os
import sys
from playwright_generation.orchestration.agent_orchestrator import PlaywrightAgentOrchestrator

async def test_with_selectors_file(test_case_id, selectors_file):
    """
    Test the PlaywrightAgentOrchestrator with existing selectors file.
    """
    print(f"🧪 Testing with selectors file: {selectors_file}")
    
    # Load selectors
    with open(selectors_file, 'r', encoding='utf-8') as f:
        selectors = json.load(f)
    
    # Create a minimal test case
    test_case = {
        "id": test_case_id,
        "title": f"Test case {test_case_id}",
        "steps": "Login to the application and create an environment",
        "expectedResults": "Environment should be created successfully",
        "loginUrl": os.getenv("APP_URL", "https://example.com"),
        "username": os.getenv("APP_USERNAME", "testuser"),
        "password": os.getenv("APP_PASSWORD", "password")
    }
    
    # Initialize orchestrator
    output_dir = os.path.join("test_output", test_case_id)
    orchestrator = PlaywrightAgentOrchestrator(output_dir=output_dir)
    
    # USE THE NEW METHOD with message-based agents
    success = await orchestrator.generate_from_selectors(test_case_id, test_case, selectors)
    
    if success:
        print(f"✅ Test successful - generated files in {output_dir}")
    else:
        print(f"❌ Test failed - check logs for details")
        
if __name__ == "__main__":
    # Get test case ID from command line
    if len(sys.argv) < 2:
        print("Usage: python test_orchestrator.py <TEST_CASE_ID>")
        sys.exit(1)
    
    test_case_id = sys.argv[1]
    selectors_file = f"{test_case_id}_selectors.json"
    
    # Check if selectors file exists
    if not os.path.exists(selectors_file):
        print(f"❌ Selectors file not found: {selectors_file}")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_with_selectors_file(test_case_id, selectors_file))