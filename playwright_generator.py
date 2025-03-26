#!/usr/bin/env python3
import argparse
import asyncio
import os
import sys

# Add the current directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from playwright_automation.generator import generate_scripts_for_feature, generate_script_for_test_case


async def main():
    """
    Main entry point for the Playwright test generator.
    Parses command line arguments and initiates the generation process.
    """
    parser = argparse.ArgumentParser(description="Generate Playwright tests from existing test cases")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Feature command - generate scripts for an entire feature
    feature_parser = subparsers.add_parser("feature", help="Generate tests for a feature")
    feature_parser.add_argument("feature_id", help="ID of the feature (e.g., FEAT-ENV-001)")
    feature_parser.add_argument("--force", action="store_true", help="Force regeneration of all scripts")
    
    # Test case command - generate a script for a specific test case
    test_parser = subparsers.add_parser("test", help="Generate a test for a specific test case")
    test_parser.add_argument("test_case_id", help="ID of the test case (e.g., TC-ENV-001)")
    test_parser.add_argument("--force", action="store_true", help="Force regeneration of the script")
    
    # Setup command - initialize the Playwright testing environment
    setup_parser = subparsers.add_parser("setup", help="Set up the Playwright testing environment")
    
    # List command - list all generated tests
    list_parser = subparsers.add_parser("list", help="List all generated tests")
    list_parser.add_argument("--feature", help="Filter by feature ID")
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Create base directories if they don't exist
    base_dir = os.path.abspath("playwright_tests")
    os.makedirs(os.path.join(base_dir, "pages"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "tests"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "utils"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "metadata"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "backups"), exist_ok=True)
    
    # Import internal modules
    from playwright_automation.utils import create_playwright_config, format_console_output
    from playwright_automation.script_manager import get_all_test_scripts
    
    # Create Playwright config if it doesn't exist
    create_playwright_config()
    
    # Execute the appropriate command
    if args.command == "feature":
        print(format_console_output("info", f"Generating Playwright tests for feature: {args.feature_id}"))
        await generate_scripts_for_feature(args.feature_id, force_update=args.force)
    
    elif args.command == "test":
        print(format_console_output("info", f"Generating Playwright test for test case: {args.test_case_id}"))
        await generate_script_for_test_case(args.test_case_id, force_update=args.force)
    
    elif args.command == "setup":
        # Initialize the Playwright testing environment
        try:
            print(format_console_output("info", "Setting up Playwright environment..."))
            
            # Check if package.json exists
            package_json_path = os.path.join(base_dir, "package.json")
            if not os.path.exists(package_json_path):
                # Create basic package.json
                with open(package_json_path, "w", encoding="utf-8") as f:
                    f.write("""{
  "name": "playwright-tests",
  "version": "1.0.0",
  "description": "Generated Playwright tests",
  "scripts": {
    "test": "playwright test",
    "test:headed": "playwright test --headed",
    "test:ui": "playwright test --ui"
  },
  "dependencies": {
    "@playwright/test": "^1.40.0"
  }
}
""")
                print(format_console_output("success", "Created package.json"))
            
            # Create .gitignore if it doesn't exist
            gitignore_path = os.path.join(base_dir, ".gitignore")
            if not os.path.exists(gitignore_path):
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write("""node_modules/
/test-results/
/playwright-report/
/playwright/.cache/
.env
""")
                print(format_console_output("success", "Created .gitignore"))
            
            # Create README.md if it doesn't exist
            readme_path = os.path.join(base_dir, "README.md")
            if not os.path.exists(readme_path):
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write("""# Generated Playwright Tests

This directory contains automatically generated Playwright tests based on test cases from the vector database.

## Setup

1. Install dependencies:
   ```
   npm install
   ```

2. Install Playwright browsers:
   ```
   npx playwright install
   ```

## Running Tests

Run all tests:
```
npm test
```

Run with browser visible:
```
npm run test:headed
```

Run in UI mode:
```
npm run test:ui
```
""")
                print(format_console_output("success", "Created README.md"))
            
            print(format_console_output("success", "Playwright environment set up successfully"))
            print(format_console_output("info", "Next steps:"))
            print(format_console_output("info", "1. cd playwright_tests"))
            print(format_console_output("info", "2. npm install"))
            print(format_console_output("info", "3. npx playwright install"))
            
        except Exception as e:
            print(format_console_output("error", f"Error setting up Playwright environment: {str(e)}"))
    
    elif args.command == "list":
        # List all generated tests
        scripts = get_all_test_scripts()
        
        # Filter by feature if specified
        if hasattr(args, 'feature') and args.feature:
            scripts = [s for s in scripts if args.feature.upper() in s["id"]]
        
        if scripts:
            print(format_console_output("info", f"Found {len(scripts)} generated test scripts:"))
            for script in scripts:
                print(f"  - {script['id']} ({script['relative_path']})")
        else:
            print(format_console_output("info", "No test scripts found"))
    
    else:
        parser.print_help()
        
    print(format_console_output("success", "Playwright test generation completed"))


if __name__ == "__main__":
    asyncio.run(main())