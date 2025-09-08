"""
Optimized MCP automation execution with structured login and better error handling
"""

import json
import os
from openai import AzureOpenAI
from mcp_helpers.mcp_manager import WorkingMCPManager

async def run_mcp_automation(test_case_id, test_case):
    """Run MCP automation using optimized approach"""
    manager = WorkingMCPManager()
    execution_log = []
    
    try:
        print("🎭 Starting MCP automation")
        await manager.start_server()
        
        execution_log = await execute_optimized_test(manager, test_case_id, test_case)
        
        # Save execution log
        with open(f"{test_case_id}_mcp_execution_log.json", "w") as f:
            json.dump(execution_log, f, indent=2)
        print(f"📄 Execution log saved to {test_case_id}_mcp_execution_log.json")
        
        return execution_log
        
    except Exception as e:
        print(f"❌ MCP automation failed: {e}")
        return None
    finally:
        await manager.cleanup()

async def execute_optimized_test(manager, test_case_id, test_case):
    """Execute test with optimized login and structured execution"""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview"
    )
    
    execution_log = []
    
    # Phase 1: Login (separate optimized flow)
    print("🔐 Phase 1: Login")
    login_log = await execute_login_phase(manager, client)
    execution_log.extend(login_log)
    
    # Phase 2: Execute test steps
    print("🧪 Phase 2: Test Execution")
    test_log = await execute_test_phase(manager, client, test_case)
    execution_log.extend(test_log)
    
    return execution_log

async def execute_login_phase(manager, client):
    """Optimized login phase with direct instructions"""
    
    login_prompt = f"""
Execute login sequence efficiently:

APPLICATION: {os.getenv('APP_URL')}
CREDENTIALS: Username={os.getenv('APP_EMAIL')}, Password={os.getenv('APP_PASSWORD')}

EXECUTE THIS EXACT SEQUENCE:
1. navigate_to: {os.getenv('APP_URL')}
2. browser_snapshot (capture login page)
3. type_text: email field with "{os.getenv('APP_EMAIL')}"
4. type_text: password field with "{os.getenv('APP_PASSWORD')}"  
5. click_element: login/submit button
6. browser_snapshot (verify login success)

STOP after login is complete and you see the main application page.
"""

    system_msg = """You are a login automation specialist. Execute login steps efficiently:

CRITICAL RULES:
- Use ONLY the ref ID (e.g., 'e21') for MCP tool parameters
- Execute steps in exact sequence provided
- Take snapshots only when specified
- STOP immediately after successful login

LOGIN TOOLS PRIORITY:
1. navigate_to - Go to login page
2. browser_snapshot - Capture current state
3. type_text - Enter credentials  
4. click_element - Click login button
5. browser_snapshot - Verify success

Focus on speed and efficiency. Do not overthink or add extra steps."""

    return await execute_phase(manager, client, login_prompt, system_msg, max_iterations=8, phase_name="LOGIN")

async def execute_test_phase(manager, client, test_case):
    """Execute main test steps after login"""
    
    # Check for structured steps
    structured_steps = test_case.get('structured_steps', [])
    
    if structured_steps:
        # Build detailed test instructions
        test_instructions = "EXECUTE THESE TEST STEPS IN ORDER:\n\n"
        for i, step in enumerate(structured_steps, 1):
            test_instructions += f"STEP {i}:\n"
            test_instructions += f"Action: {step['action']}\n"
            if step.get('expected'):
                test_instructions += f"Expected: {step['expected']}\n"
                test_instructions += f"✅ VERIFY: Take browser_snapshot and confirm {step['expected']}\n"
            test_instructions += "\n"
        
        test_instructions += f"\nOVERALL EXPECTED RESULT:\n{test_case.get('expectedResults', '')}\n"
        
        print(f"📋 Executing {len(structured_steps)} structured test steps")
    else:
        # Fallback to basic steps
        test_instructions = f"""
EXECUTE THESE TEST STEPS:
{test_case.get('steps', '')}

EXPECTED RESULTS:
{test_case.get('expectedResults', '')}
"""
        print("📋 Executing basic test steps")

    test_prompt = f"""
You are already logged into the application. Execute the test case:

{test_instructions}

IMPORTANT:
- Application is already loaded and you are logged in
- Execute ALL test steps completely
- Use browser_snapshot after each major action
- Verify results against expected outcomes
- Continue until ALL steps are completed or you encounter a blocking error
"""

    system_msg = """You are executing test steps on an already logged-in application.

EXECUTION RULES:
- User is ALREADY logged in - do not attempt login again
- Execute ALL provided test steps in sequence
- Use browser_snapshot after each significant action
- When encountering errors, try alternative approaches before giving up
- Continue until test is complete or you hit an unrecoverable error

MCP REFERENCE FORMAT:
- Extract ONLY the ref ID (e.g., 'e21') from snapshots
- Use clear, descriptive element identification
- Handle dynamic elements gracefully

PERSISTENCE STRATEGY:
- If an element is not found, take a snapshot to see current page state
- Try alternative locators (text, role, label)
- Wait for elements to load if needed
- Report specific errors with context"""

    return await execute_phase(manager, client, test_prompt, system_msg, max_iterations=20, phase_name="TEST")

async def execute_phase(manager, client, prompt, system_msg, max_iterations, phase_name):
    """Execute a specific phase with proper error handling"""
    
    conversation_history = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]
    
    phase_log = []
    iteration = 0
    consecutive_errors = 0
    max_consecutive_errors = 3

    print(f"🚀 Starting {phase_name} phase...")

    while iteration < max_iterations:
        iteration += 1
        print(f"--- {phase_name} Iteration {iteration}/{max_iterations} ---")

        try:
            # Get available tools
            tools = []
            for tool in manager.available_tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool['name'],
                        "description": tool.get('description', ''),
                        "parameters": tool.get('inputSchema', {"type": "object", "properties": {}})
                    }
                })

            # Make API call
            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                messages=conversation_history,
                tools=tools,
                tool_choice="auto",
                temperature=0
            )

            message = response.choices[0].message
            
            # Add assistant message to history
            conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls if message.tool_calls else None
            })

            # Execute tool calls if any
            if message.tool_calls:
                tools_executed = 0
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON decode error: {e}")
                        args = {}
                    
                    # Execute tool
                    result = await manager.execute_tool(tool_name, args)
                    tools_executed += 1
                    
                    # Log execution
                    log_entry = {
                        "phase": phase_name,
                        "iteration": iteration,
                        "tool": tool_name,
                        "args": args,
                        "result": result.get("result", {}),
                        "success": "error" not in result,
                        "timestamp": iteration
                    }
                    phase_log.append(log_entry)

                    # Add tool result to conversation
                    conversation_history.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })
                
                print(f"✅ Executed {tools_executed} tools")
                consecutive_errors = 0  # Reset error counter on successful execution
                
            else:
                # AI has finished this phase
                print(f"🎯 {phase_name} phase completed: {message.content}")
                
                # Check if this is actual completion or premature exit
                if phase_name == "LOGIN" and "login" in message.content.lower():
                    print("✅ Login phase completed successfully")
                    break
                elif phase_name == "TEST" and any(word in message.content.lower() for word in ["completed", "finished", "done", "success"]):
                    print("✅ Test phase completed successfully")
                    break
                else:
                    # Encourage continuation if it seems incomplete
                    if iteration < max_iterations - 2:  # Don't add if near limit
                        conversation_history.append({
                            "role": "user",
                            "content": "Continue with the next step if there are more actions to perform."
                        })
                        continue
                    else:
                        print("⚠️ Reached iteration limit")
                        break

        except Exception as e:
            print(f"❌ Error in {phase_name} iteration {iteration}: {e}")
            consecutive_errors += 1
            
            # Add error recovery
            error_log = {
                "phase": phase_name,
                "iteration": iteration,
                "error": str(e),
                "consecutive_errors": consecutive_errors
            }
            phase_log.append(error_log)
            
            # If too many consecutive errors, try to recover
            if consecutive_errors >= max_consecutive_errors:
                print(f"🔄 Too many consecutive errors, attempting recovery...")
                conversation_history.append({
                    "role": "user", 
                    "content": "There have been errors. Please take a browser_snapshot to see the current state and continue from there."
                })
                consecutive_errors = 0  # Reset counter after recovery attempt
            
            continue

    print(f"📊 {phase_name} phase completed after {iteration} iterations")
    return phase_log