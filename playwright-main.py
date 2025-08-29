#!/usr/bin/env python3
"""
Simple main entry point for the Playwright Test Generator.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import asyncio
from dotenv import load_dotenv
from playwright_generation.runners.standalone_test_generator import generate_test

# Load environment variables
load_dotenv()

async def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python playwright-main.py <TEST_CASE_ID> [output_dir]")
        return
    
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "playwright_tests"
    
    # Import the standalone test generator
    
    
    print(f"🚀 Generating test for {test_case_id}")
    success = await generate_test(
        test_case_id=test_case_id,
        output_dir=output_dir,
        use_design_first=True
    )
    
    if success:
        print(f"✅ Successfully generated test for {test_case_id}")
    else:
        print(f"❌ Failed to generate test for {test_case_id}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())