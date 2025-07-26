#!/usr/bin/env python3
"""
Quick fix for the execution_log KeyError
"""

def fix_agent_specialized():
    """Fix the agent_specialized.py file to properly handle execution_log"""
    
    print("=== FIXING AGENT_SPECIALIZED.PY ===")
    
    try:
        # Read the file
        with open('playwright_generation/orchestration/agent_specialized.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Debug: Check what's in the initial_state
        print("Looking for initial_state definition...")
        
        # Find the initial_state definition and show it
        import re
        state_match = re.search(r'initial_state = \{.*?\}', content, re.DOTALL)
        if state_match:
            print("Found initial_state:")
            print(state_match.group(0))
        
        # The issue is that we need to update ALL references to selectors
        # Let's do a comprehensive find and replace
        
        # 1. Update the TestGenerationState class if it exists
        if 'selectors: list' in content:
            content = content.replace('selectors: list', 'execution_log: list')
            print("✅ Updated TestGenerationState")
        
        # 2. Make sure initial_state has execution_log
        old_initial_state_pattern = r'initial_state = \{\s*"test_case_id": test_case_id,\s*"test_case": test_case,\s*"selectors": selectors,'
        new_initial_state = '''initial_state = {
            "test_case_id": test_case_id,
            "test_case": test_case,
            "execution_log": execution_log,'''
        
        content = re.sub(old_initial_state_pattern, new_initial_state, content)
        
        # 3. Update any remaining selectors references in comments or other places
        content = content.replace('"selectors": selectors', '"execution_log": execution_log')
        content = content.replace('selectors (list): List of selector data', 'execution_log (list): MCP execution log with actual browser interactions')
        
        # Write back
        with open('playwright_generation/orchestration/agent_specialized.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Fixed agent_specialized.py")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing agent_specialized.py: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_current_state():
    """Check what's currently in the initial_state"""
    
    print("\n=== CHECKING CURRENT STATE ===")
    
    try:
        with open('playwright_generation/orchestration/agent_specialized.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find and show the initial_state
        import re
        
        # Look for the initial_state in the generate_with_specialized_agents function
        function_match = re.search(r'async def generate_with_specialized_agents.*?initial_state = \{.*?\}', content, re.DOTALL)
        if function_match:
            print("Found function with initial_state:")
            lines = function_match.group(0).split('\n')
            for i, line in enumerate(lines):
                if 'initial_state' in line or (i > 0 and 'initial_state' in lines[i-1]):
                    print(f"  {line}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking state: {e}")
        return False

def test_import():
    """Test if the fixed module imports correctly"""
    
    print("\n=== TESTING IMPORT ===")
    
    try:
        import sys
        
        # Remove from cache if already imported
        if 'playwright_generation.orchestration.agent_specialized' in sys.modules:
            del sys.modules['playwright_generation.orchestration.agent_specialized']
        
        # Try importing
        from playwright_generation.orchestration.agent_specialized import generate_with_specialized_agents
        
        print("✅ Import successful")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Fixing execution_log KeyError...")
    
    check_current_state()
    success = fix_agent_specialized()
    
    if success:
        success = test_import()
    
    if success:
        print("\n🎉 Fix applied successfully!")
        print("Now try running the test again:")
        print("python -m playwright_generation.generators.mcp_test_generator TC-ENV-001")
    else:
        print("\n❌ Fix failed - need to debug further")