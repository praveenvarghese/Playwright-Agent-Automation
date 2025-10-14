"""
Main test runner with optimized execution flow including logout phase
TOKEN OPTIMIZATION APPLIED - Production Ready
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project paths for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_helpers.automation_runner import run_mcp_automation
from test_config import TestConfig, TestStepParser, ExecutionMonitor

async def main():
    """Main execution function with token optimization"""
    
    # Validate environment
    try:
        TestConfig.validate_environment()
        print("✅ Environment validation passed")
    except ValueError as e:
        print(f"❌ Environment validation failed: {e}")
        return 1
    
    # Load test case
    test_case_file = sys.argv[1] if len(sys.argv) > 1 else "test_case.json"
    
    try:
        with open(test_case_file, 'r', encoding='utf-8') as f:
            test_case_data = json.load(f)
        print(f"📋 Loaded test case from {test_case_file}")
    except FileNotFoundError:
        print(f"❌ Test case file not found: {test_case_file}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in test case file: {e}")
        return 1
    
    # Parse and optimize test case
    test_case_id = test_case_data.get('id', 'unknown_test')
    test_case = TestStepParser.parse_test_case(test_case_data)
    
    print(f"🎯 Executing test case: {test_case_id}")
    print(f"📝 Test description: {test_case.get('title', 'No description')}")
    
    # Pre-flight token optimization check
    structured_steps = test_case.get('structured_steps', [])
    if len(structured_steps) > int(os.getenv('MCP_CHUNK_SIZE', '20')):
        print(f"📦 Large test detected ({len(structured_steps)} steps)")
        print("🔧 Token optimization and chunking will be applied")
    
    # Estimate input size
    test_case_json = json.dumps(test_case_data)
    input_tokens = len(test_case_json) // 4  # Rough token estimation
    print(f"📏 Input test size: {input_tokens} estimated tokens")
    
    # Initialize monitoring
    monitor = ExecutionMonitor()
    monitor.log_token_usage(input_tokens)
    
    # Run the automation with token optimization
    start_time = datetime.now()
    print(f"⏱️ Test execution started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        execution_log = await run_mcp_automation(test_case_id, test_case)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        print(f"⏱️ Test execution completed in {duration}")
        
        if execution_log:
            # Analyze results based on format type
            if isinstance(execution_log, dict) and "steps" in execution_log:
                # New compact format
                analyze_compact_execution_results(execution_log, monitor)
            elif isinstance(execution_log, list):
                # Legacy format support
                analyze_execution_results(execution_log, monitor)
            else:
                print("⚠️ Unknown execution log format")
            
            print("✅ Test execution completed successfully")
            return 0
        else:
            print("❌ Test execution failed or returned no results")
            return 1
            
    except Exception as e:
        print(f"💥 Fatal error during test execution: {e}")
        import traceback
        traceback.print_exc()
        return 1

def analyze_compact_execution_results(compact_log, monitor):
    """Analyze compact execution results (token-optimized format)"""
    
    if not compact_log:
        print("⚠️ No execution log available")
        return
    
    metadata = compact_log.get("metadata", {})
    phases = compact_log.get("phases", {})
    steps = compact_log.get("steps", [])
    
    print("\n📊 COMPACT EXECUTION ANALYSIS")
    print("=" * 50)
    
    # Token efficiency analysis
    estimated_tokens = metadata.get("total_tokens_estimate", 0)
    if estimated_tokens > 0:
        print(f"🎯 TOKEN EFFICIENCY:")
        print(f"   Estimated tokens: {estimated_tokens}")
        if estimated_tokens < 20000:
            efficiency_rating = "EXCELLENT"
        elif estimated_tokens < 30000:
            efficiency_rating = "GOOD"
        else:
            efficiency_rating = "NEEDS_OPTIMIZATION"
        print(f"   Token efficiency: {efficiency_rating}")
        
        # Update monitor
        monitor.log_token_usage(estimated_tokens)
    
    # Phase analysis with duration tracking
    total_duration = 0
    for phase_name, phase_data in phases.items():
        status = phase_data.get("status", "unknown")
        duration_ms = phase_data.get("duration_ms", 0)
        duration_s = duration_ms / 1000
        total_duration += duration_ms
        
        print(f"📋 {phase_name.title()} Phase: {status} ({duration_s:.1f}s)")
        
        if phase_name == "test":
            executed = phase_data.get("executed_steps", 0)
            total_steps = phase_data.get("total_steps", 0)
            if total_steps > 0:
                completion_rate = (executed / total_steps) * 100
                print(f"   Steps: {executed}/{total_steps} ({completion_rate:.1f}% completed)")
                
                # Check for partial execution
                if executed < total_steps:
                    print(f"   ⚠️ Partial execution detected - may need continuation")
        
        # Log phase completion
        monitor.log_phase_completion(phase_name, status == "completed")
    
    # Steps summary with status breakdown
    if steps:
        completed_steps = [s for s in steps if s.get("status") == "completed"]
        pending_steps = [s for s in steps if s.get("status") == "pending"]
        failed_steps = [s for s in steps if s.get("status") == "failed"]
        
        print(f"\n📝 STEP SUMMARY:")
        print(f"   Total steps: {len(steps)}")
        print(f"   Completed: {len(completed_steps)}")
        if pending_steps:
            print(f"   Pending: {len(pending_steps)}")
        if failed_steps:
            print(f"   Failed: {len(failed_steps)}")
            
        # Success rate calculation
        if len(steps) > 0:
            success_rate = (len(completed_steps) / len(steps)) * 100
            print(f"   Success Rate: {success_rate:.1f}%")
        
        # Check for continuation needs
        if pending_steps or failed_steps:
            print(f"   💡 Recommendation: Review failed/pending steps for continuation")
    
    # External logging information
    external_log_path = metadata.get("external_log_path")
    if external_log_path and os.path.exists(external_log_path):
        external_size = os.path.getsize(external_log_path)
        print(f"\n📄 EXTERNAL LOGS:")
        print(f"   Path: {external_log_path}")
        print(f"   Size: {external_size} bytes")
        print(f"   Full debugging data preserved externally")
    
    # Performance summary
    if total_duration > 0:
        avg_step_time = (total_duration / max(len(steps), 1)) / 1000
        print(f"\n⚡ PERFORMANCE:")
        print(f"   Total duration: {total_duration/1000:.1f}s")
        print(f"   Average step time: {avg_step_time:.1f}s")

def analyze_execution_results(execution_log, monitor):
    """Analyze execution results (legacy format support)"""
    
    if not execution_log:
        print("⚠️ No execution log available")
        return
    
    # Count phases and iterations
    login_iterations = len([log for log in execution_log if log.get('phase') == 'LOGIN'])
    test_iterations = len([log for log in execution_log if log.get('phase') == 'TEST'])
    logout_iterations = len([log for log in execution_log if log.get('phase') == 'LOGOUT'])
    total_tools = len([log for log in execution_log if log.get('tool')])
    successful_tools = len([log for log in execution_log if log.get('success', False)])
    
    print("\n📊 EXECUTION ANALYSIS (Legacy Format)")
    print("=" * 50)
    print(f"🔐 Login Phase: {login_iterations} iterations")
    print(f"🧪 Test Phase: {test_iterations} iterations") 
    print(f"🚪 Logout Phase: {logout_iterations} iterations")
    print(f"🔧 Total Tools Executed: {total_tools}")
    print(f"✅ Successful Tools: {successful_tools}")
    if total_tools > 0:
        success_rate = (successful_tools / total_tools) * 100
        print(f"📈 Success Rate: {success_rate:.1f}%")
    
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
    
    # Phase-specific analysis
    phase_analysis = analyze_phases(execution_log)
    if phase_analysis:
        print(f"\n📋 PHASE ANALYSIS:")
        for phase, stats in phase_analysis.items():
            print(f"  {phase}: {stats['tools']} tools, {stats['success_rate']:.1f}% success")
    
    # Check for common issues
    errors = [log for log in execution_log if log.get('error')]
    if errors:
        print(f"\n⚠️ ERRORS ENCOUNTERED: {len(errors)}")
        for error in errors[-3:]:  # Show last 3 errors
            phase = error.get('phase', 'Unknown')
            error_msg = error.get('error', 'Unknown error')
            print(f"  - {phase}: {error_msg}")
    
    # Performance recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    
    if login_iterations > 8:
        print(f"  - Login took {login_iterations} iterations (expected: 4-8)")
        print(f"    Consider optimizing login flow")
    
    if test_iterations > 20:
        print(f"  - Test execution took {test_iterations} iterations")
        print(f"    Consider using token optimization and chunking")
    
    if logout_iterations > 8:
        print(f"  - Logout took {logout_iterations} iterations (expected: 3-6)")
        print(f"    Check logout element selectors")
    
    if total_tools > 0:
        success_rate = (successful_tools / total_tools) * 100
        if success_rate < 80:
            print(f"  - Success rate is {success_rate:.1f}% (target: >90%)")
            print(f"    Review element selectors and timing")
    
    # Complete flow validation
    phases_completed = set(log.get('phase') for log in execution_log if log.get('phase'))
    expected_phases = {'LOGIN', 'TEST', 'LOGOUT'}
    
    if phases_completed == expected_phases:
        print(f"  ✅ Complete flow executed: Login → Test → Logout")
    else:
        missing_phases = expected_phases - phases_completed
        if missing_phases:
            print(f"  ⚠️ Missing phases: {', '.join(missing_phases)}")

def analyze_phases(execution_log):
    """Analyze performance of each phase"""
    phase_stats = {}
    
    for log in execution_log:
        phase = log.get('phase')
        if not phase or not log.get('tool'):
            continue
            
        if phase not in phase_stats:
            phase_stats[phase] = {'tools': 0, 'successful': 0}
        
        phase_stats[phase]['tools'] += 1
        if log.get('success', False):
            phase_stats[phase]['successful'] += 1
    
    # Calculate success rates
    for phase in phase_stats:
        total = phase_stats[phase]['tools']
        successful = phase_stats[phase]['successful']
        phase_stats[phase]['success_rate'] = (successful / max(1, total)) * 100
    
    return phase_stats

def create_sample_test_case():
    """Create a sample test case file with token optimization in mind"""
    
    sample_test = {
        "id": "sample_test_001",
        "title": "Sample Login and Navigation Test with Token Optimization",
        "description": "Test login and basic navigation functionality with logout - optimized for token efficiency",
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
            },
            {
                "step": 4,
                "action": "Click on admin user to view details",
                "expected": "User details page opens"
            },
            {
                "step": 5,
                "action": "Navigate back to users list",
                "expected": "Users list page is displayed"
            }
        ],
        "expectedResults": "User should be able to login, navigate to users page, perform search, view details, and logout successfully",
        "priority": "High",
        "category": "Smoke Test",
        "token_optimization": {
            "chunking_recommended": False,
            "estimated_complexity": "Low"
        }
    }
    
    with open("sample_test_case.json", "w", encoding='utf-8') as f:
        json.dump(sample_test, f, indent=2)
    
    print("📝 Sample test case created: sample_test_case.json")

def show_usage():
    """Show usage information"""
    print("Usage:")
    print(f"  python {sys.argv[0]} <test_case_file.json>")
    print(f"  python {sys.argv[0]} --create-sample")
    print()
    print("Environment Variables (set in .env file):")
    print("  MCP_CHUNK_SIZE=20              # Steps per chunk")
    print("  MCP_MAX_TOKENS=25000          # Token limit per chunk")  
    print("  LOG_RETENTION_DAYS=7          # External log retention")
    print()
    print("Example test case structure:")
    
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
        "expectedResults": "Overall expected outcome including logout"
    }
    
    print(json.dumps(example, indent=2))

if __name__ == "__main__":
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--create-sample":
        create_sample_test_case()
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        show_usage()
        sys.exit(0)
    
    # Check if test case file exists
    test_case_file = sys.argv[1] if len(sys.argv) > 1 else "test_case.json"
    
    if not os.path.exists(test_case_file):
        print(f"❌ Test case file not found: {test_case_file}")
        print()
        show_usage()
        sys.exit(1)
    
    # Show token optimization status
    print("🔧 TOKEN OPTIMIZATION STATUS:")
    print(f"   Chunk Size: {os.getenv('MCP_CHUNK_SIZE', 'Not set (default: 20)')}")
    print(f"   Max Tokens: {os.getenv('MCP_MAX_TOKENS', 'Not set (default: 25000)')}")
    print(f"   Log Retention: {os.getenv('LOG_RETENTION_DAYS', 'Not set (default: 7)')} days")
    print()
    
    # Run the test
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)