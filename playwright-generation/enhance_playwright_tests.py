#!/usr/bin/env python3
"""
Main script for enhancing Playwright tests with AI agents.
This script can be used to enhance existing Playwright tests or generate new ones.
"""

import os
import sys
import argparse
import asyncio
from dotenv import load_dotenv

def setup_environment():
    """Set up environment and load required modules."""
    # Add ai_enhanced_pw directory to path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(script_dir)
    
    # Load environment variables
    load_dotenv()
    
    # Check if required environment variables are set
    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Enhance Playwright tests with AI agents")
    
    parser.add_argument(
        "test_case_id",
        help="Test case ID (e.g., TC-ENV-001)"
    )
    
    parser.add_argument(
        "--mode",
        choices=["enhance", "generate"],
        default="generate",
        help="Mode: 'enhance' existing test or 'generate' and enhance (default: generate)"
    )
    
    parser.add_argument(
        "--script",
        help="Path to existing Playwright script (required for enhance mode)"
    )
    
    parser.add_argument(
        "--selectors",
        help="Path to selectors JSON file (required for enhance mode)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="enhanced_playwright_tests",
        help="Output directory for enhanced tests (default: enhanced_playwright_tests)"
    )
    
    return parser.parse_args()

async def main():
    """Main entry point."""
    # Set up environment
    setup_environment()
    
    # Parse arguments
    args = parse_arguments()
    
    # Import after environment setup
    from integration import enhance_playwright_script, generate_and_enhance
    
    if args.mode == "enhance":
        # Enhance existing script
        if not args.script or not args.selectors:
            print("❌ Error: --script and --selectors are required for enhance mode")
            sys.exit(1)
            
        print(f"🚀 Enhancing Playwright script: {args.script}")
        success = enhance_playwright_script(
            test_case_id=args.test_case_id,
            original_script_path=args.script,
            selectors_file_path=args.selectors,
            output_dir=args.output_dir
        )
    else:
        # Generate and enhance
        print(f"🚀 Generating and enhancing Playwright script for {args.test_case_id}")
        success = generate_and_enhance(
            test_case_id=args.test_case_id
        )
    
    if success:
        print(f"✅ Successfully enhanced Playwright test for {args.test_case_id}")
        print(f"📁 Enhanced files are in directory: {args.output_dir}")
        sys.exit(0)
    else:
        print(f"❌ Failed to enhance Playwright test for {args.test_case_id}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())