"""
MCP automation with aggressive conversation history management
to avoid Azure content filter triggers
"""

import json
import os
from openai import AzureOpenAI
from mcp_helpers.mcp_manager import WorkingMCPManager
from dotenv import load_dotenv

load_dotenv()

async def run_mcp_automation(test_case_id, test_case):
    """Run MCP automation"""
    manager = WorkingMCPManager()
    
    try:
        print(f"Starting automation for {test_case_id}")
        await manager.start_server()
        
        execution_log = await execute_test(manager, test_case_id, test_case)
        
        with open(f"{test_case_id}_log.json", "w") as f:
            json.dump(execution_log, f, indent=2)
        
        return execution_log
        
    except Exception as e:
        print(f"Automation failed: {e}")
        return None
    finally:
        await manager.cleanup()

async def execute_test(manager, test_case_id, test_case):
    """Execute full test"""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview"
    )
    
    log = []
    
    print("Login phase")
    log.extend(await run_phase(manager, client, "LOGIN", create_login_instructions(), 8))
    
    print("Test phase")
    log.extend(await run_phase(manager, client, "TEST", create_test_instructions(test_case), 30))
    
    print("Logout phase")
    log.extend(await run_phase(manager, client, "LOGOUT", "Find user menu, click it, find logout, click it.", 8))
    
    return log

def create_login_instructions():
    """Login instructions"""
    return f"""Navigate to {os.getenv('APP_URL')}, type {os.getenv('APP_EMAIL')} in email field, type {os.getenv('APP_PASSWORD')} in password field, click login button."""

def create_test_instructions(test_case):
    """Test instructions"""
    steps = test_case.get('structured_steps', [])
    if not steps:
        return "Execute test steps."
    
    instructions = "Do: " + " Then: ".join([step.get('action', '') for step in steps[:5]])  # Limit to 5 steps
    return instructions

def truncate_snapshot_for_ai(snapshot_result):
    """Truncate snapshot to essential info only"""
    if not snapshot_result or "result" not in snapshot_result:
        return "Page loaded."
    
    content = snapshot_result["result"].get("content", [])
    if not content or "text" not in content[0]:
        return "Page loaded."
    
    text = content[0]["text"]
    
    # Extract only element references, drop HTML/code
    lines = text.split('\n')
    refs = []
    for line in lines[:100]:  # First 100 lines only
        if 'ref=' in line and '<e' in line:
            # Extract ref pattern
            import re
            matches = re.findall(r'<e(\d+)>([^<]+)</e\1>', line)
            for match in matches:
                refs.append(f"e{match[0]}:{match[1][:30]}")  # Ref and first 30 chars of text
    
    return "Elements: " + ", ".join(refs[:20])  # Max 20 elements

async def run_phase(manager, client, phase, instructions, max_iter):
    """Run phase with minimal conversation history"""
    
    log = []
    iteration = 0
    
    # Start fresh each iteration to avoid accumulation
    base_system = "You automate web browsers. Use navigate_to, browser_snapshot, browser_click with element and ref, browser_type with element ref and text."
    
    while iteration < max_iter:
        iteration += 1
        print(f"{phase} iteration {iteration}/{max_iter}")
        
        # Fresh conversation every 3 iterations to avoid content filter
        if iteration % 3 == 1:
            messages = [
                {"role": "system", "content": base_system},
                {"role": "user", "content": instructions}
            ]
            print("Reset conversation history")
        
        try:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t['name'],
                        "description": t.get('description', '')[:100],  # Truncate descriptions
                        "parameters": t.get('inputSchema', {})
                    }
                }
                for t in manager.available_tools
            ]
            
            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                messages=messages[-6:],  # Only keep last 6 messages
                tools=tools,
                tool_choice="auto",
                temperature=0,
                max_tokens=500  # Limit response size
            )
            
            msg = response.choices[0].message
            
            # Add assistant message (truncated)
            messages.append({
                "role": "assistant",
                "content": (msg.content or "")[:200],  # Truncate content
                "tool_calls": msg.tool_calls
            })
            
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    
                    try:
                        args = json.loads(tc.function.arguments)
                    except:
                        args = {}
                    
                    print(f"Execute: {tool_name} {args}")
                    result = await manager.execute_tool(tool_name, args)
                    
                    log.append({
                        "phase": phase,
                        "iteration": iteration,
                        "tool": tool_name,
                        "args": args,
                        "success": "error" not in str(result).lower()
                    })
                    
                    # Truncate tool result heavily
                    if tool_name == "browser_snapshot":
                        truncated_result = truncate_snapshot_for_ai(result)
                    else:
                        truncated_result = str(result)[:300]  # Max 300 chars
                    
                    messages.append({
                        "role": "tool",
                        "content": truncated_result,
                        "tool_call_id": tc.id
                    })
                
                print(f"Executed {len(msg.tool_calls)} tools")
                
            else:
                # No tools, check if done
                if msg.content and any(w in msg.content.lower() for w in ["complete", "done", "success", "logged"]):
                    print(f"{phase} complete")
                    break
                
                # Continue
                messages.append({"role": "user", "content": "Continue."})
                
        except Exception as e:
            error_msg = str(e)
            print(f"Error: {error_msg[:100]}")
            
            log.append({
                "phase": phase,
                "iteration": iteration,
                "error": error_msg[:200]
            })
            
            # If content filter, reset completely
            if "content_filter" in error_msg.lower() or "jailbreak" in error_msg.lower():
                print("Content filter triggered - resetting")
                messages = [
                    {"role": "system", "content": base_system},
                    {"role": "user", "content": "Take snapshot and continue."}
                ]
            
            continue
    
    print(f"{phase} completed after {iteration} iterations")
    return log