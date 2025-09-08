"""
Main test runner with optimized execution flow
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from automation_runner import run_mcp_automation
from test_config import TestConfig, TestStepParser, ExecutionMonitor

async def main():
    """Main execution function"""
    
    # Validate environment
    try:
        TestConfig.validate_environment()
        print("✅ Environment validation passed")
    except ValueError as e:
        print(f"❌ Environment validation failed: {e}")
        return
    
    # Load test case
    test_case_file = sys.argv[1] if len(sys.argv) > 1 else "test_case.json"
    
    try:
        with open(test_case_file, 'r') as f:
            test_case_data = json.load(f)
        print(f"📋 Loaded test case from {test_case_file}")
    except FileNotFoundError:
        print(f"❌ Test case file not found: {test_case_file}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in test case file: {e}")
        return
    
    # Parse and optimize test case
    test_case_id = test_case_data.get('id', 'unknown_test')
    test_case = TestStepParser.parse_test_case(test_case_data)
    
    print(f"🎯 Executing test case: {test_case_id}")
    print(f"📝 Test description: {test_case.get('title', 'No description')}")
    
    # Initialize monitoring
    monitor = ExecutionMonitor()
    
    # Run the automation
    start_time = datetime.now()
    print(f"⏱️ Test execution started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        execution_log = await run_mcp_automation(test_case_id, test_case)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        print(f"⏱️ Test execution completed in {duration}")
        
        if execution_log:
            # Analyze results
            analyze_execution_results(execution_log, monitor)
            print("✅ Test execution completed successfully")
            return 0
        else:
            print("❌ Test execution failed")
            return 1
            
    except Exception as e:
        print(f"💥 Fatal error during test execution: {e}")
        return 1

def analyze_execution_results(execution_log, monitor):
    """Analyze execution results and provide insights"""
    
    if not execution_log:
        print("⚠️ No execution log available")
        return
    
    # Count phases and iterations
    login_iterations = len([log for log in execution_log if log.get('phase') == 'LOGIN'])
    test_iterations = len([log for log in execution_log if log.get('phase') == 'TEST'])
    total_tools = len([log for log in execution_log if log.get('tool')])
    successful_tools = len([log for log in execution_log if log.get('success', False)])
    
    print("\n📊 EXECUTION ANALYSIS")
    print("=" * 50)
    print(f"🔐 Login Phase: {login_iterations} iterations")
    print(f"🧪 Test Phase: {test_iterations} iterations") 
    print(f"🔧 Total Tools Executed: {total_tools}")
    print(f"✅ Successful Tools: {successful_tools}")
    print(f"📈 Success Rate: {(successful_tools/max(1,total_tools))*100:.1f}%")
    
    # Identify most used tools
    tool_usage = {}
    for log in execution_log:
        if log.get('tool'):
            tool = log['tool']
            tool_usage[tool] = tool_usage.get(tool, 0) + 1
    
    if tool_usage:
        print(f"\n🔧 TOOL USAGE:")
        for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
            print(f"  {tool}: {count} times")
    
    # Check for common issues
    errors = [log for log in execution_log if log.get('error')]
    if errors:
        print(f"\n⚠️ ERRORS ENCOUNTERED: {len(errors)}")
        for error in errors[-3:]:  # Show last 3 errors
            print(f"  - {error.get('error', 'Unknown error')}")
    
    # Performance recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    
    if login_iterations > 6:
        print(f"  - Login took {login_iterations} iterations (expected: 4-6)")
        print(f"    Consider optimizing login flow or checking credentials")
    
    if test_iterations > 15:
        print(f"  - Test execution took {test_iterations} iterations")
        print(f"    Consider breaking down complex test steps")
    
    success_rate = (successful_tools/max(1,total_tools))*100
    if success_rate < 80:
        print(f"  - Success rate is {success_rate:.1f}% (target: >90%)")
        print(f"    Check element selectors and page load timing")
    
    if tool_usage.get('browser_snapshot', 0) > total_tools * 0.4:
        print(f"  - High snapshot usage detected")
        print(f"    Consider reducing verification frequency for better performance")

def create_sample_test_case():
    """Create a sample test case file"""
    
    sample_test = {
        "id": "sample_test_001",
        "title": "Sample Login and Navigation Test",
        "description": "Test login and basic navigation functionality",
        "structured_steps": [
            {
                "step": 1,
                "action": "Navigate to dashboard page",
                "expected": "Dashboard page loads with navigation menu"
            },
            {
                "step": 2, 
                "action": "Click on Users menu item",
                "expected": "Users page opens showing user list"
            },
            {
                "step": 3,
                "action": "Search for user 'admin'",
                "expected": "Search results show admin user"
            }
        ],
        "expectedResults": "User should be able to login and navigate to users page successfully",
        "priority": "High",
        "category": "Smoke Test"
    }
    
    with open("sample_test_case.json", "w") as f:
        json.dump(sample_test, f, indent=2)
    
    print("📝 Sample test case created: sample_test_case.json")

if __name__ == "__main__":
    
    # Check if user wants to create sample test case
    if len(sys.argv) > 1 and sys.argv[1] == "--create-sample":
        create_sample_test_case()
        sys.exit(0)
    
    # Check if test case file exists
    test_case_file = sys.argv[1] if len(sys.argv) > 1 else "test_case.json"
    
    if not os.path.exists(test_case_file):
        print(f"❌ Test case file not found: {test_case_file}")
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <test_case_file.json>")
        print(f"  python {sys.argv[0]} --create-sample")
        print("\nExample test case structure:")
        
        example = {
            "id": "test_001",
            "title": "Your Test Title", 
            "structured_steps": [
                {
                    "step": 1,
                    "action": "Click on Settings button",
                    "expected": "Settings page opens"
                }
            ],
            "expectedResults": "Overall expected outcome"
        }
        
        print(json.dumps(example, indent=2))
        sys.exit(1)
    
    # Run the test
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)