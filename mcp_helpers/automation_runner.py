"""
MCP automation execution with conditional verification
"""

import json
import os
from openai import AzureOpenAI
from mcp_helpers.mcp_manager import WorkingMCPManager

async def run_mcp_automation(test_case_id, test_case):
    """Run MCP automation using proven approach"""
    manager = WorkingMCPManager()
    execution_log = []
    
    try:
        print("🎭 Starting MCP automation")
        await manager.start_server()
        
        execution_log = await execute_with_conditional_verification(manager, test_case_id, test_case)
        
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

async def execute_with_conditional_verification(manager, test_case_id, test_case):
    """Execute test with conditional verification based on Azure DevOps expected results"""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview"
    )
    
    # Check for structured steps with expected results
    structured_steps = test_case.get('structured_steps', [])
    
    if structured_steps:
        # Build conditional verification instructions
        detailed_steps = "\n🎯 EXECUTE EACH STEP WITH CONDITIONAL VERIFICATION:\n"
        for step in structured_steps:
            detailed_steps += f"\n--- STEP {step['step']} ---\n"
            detailed_steps += f"ACTION: {step['action']}\n"
            if step.get('expected'):
                detailed_steps += f"EXPECTED RESULT: {step['expected']}\n"
                detailed_steps += f"🔍 AFTER ACTION: Take browser_snapshot and verify that {step['expected']}\n"
                detailed_steps += f"📝 EXPLAIN: Compare the snapshot with expected result and explain if it matches\n"
            else:
                detailed_steps += f"🔍 AFTER ACTION: Take browser_snapshot to capture current state for logging\n"
        step_instructions = detailed_steps
        print(f"📋 Using {len(structured_steps)} structured steps with conditional verification")
    else:
        # Fallback to basic steps
        step_instructions = f"\nTEST STEPS:\n{test_case.get('steps', '')}"
        print("📋 Using basic steps format")
    
    test_prompt = f"""
Execute this test case step by step with conditional verification:

CONTEXT:
- Application URL: {os.getenv('APP_URL')}
- Username: {os.getenv('APP_USERNAME')}
- Password: {os.getenv('APP_PASSWORD')}

🚨 CRITICAL INSTRUCTIONS:
1. Use Playwright locator methods for all interactions (getByRole, getByText, getByLabel)
2. When using MCP tools with 'ref' parameter, use ONLY the short ID (e.g., 'e21', not 'textbox "Username" [ref=e21]')
3. After EACH action, use browser_snapshot to capture page state
4. IF step has EXPECTED RESULT: Compare snapshot with expected and explain if it matches
5. IF step has NO expected result: Just capture snapshot for logging

REFERENCE FORMAT EXAMPLE:
From snapshot: `- textbox "Username" [active] [ref=e21]`
Correct ref: `"e21"`
Wrong ref: `"textbox \"Username\" [active] [ref=e21]"`

Execute all steps from the MCP log as part of the main test workflow, including login actions.

{step_instructions}

OVERALL EXPECTED RESULTS:
{test_case.get('expectedResults', '')}

Continue until all test steps are completed or you encounter an error.
"""

    system_msg = """You are executing a test case using Playwright MCP tools with conditional verification.

🚨 CRITICAL MCP REFERENCE FORMAT:
When using MCP tools that require 'ref' parameter:
- ONLY use the short reference ID (e.g., 'e21', 'e26', 'e27')  
- DO NOT use the full description like 'textbox "Password" [ref=e26]'
- Extract ONLY the 'e' number from the snapshot

Example from snapshot:
```yaml
- textbox "Username" [active] [ref=e21]
```
Correct tool call:
```json
{"element": "Username", "ref": "e21", "text": "admin"}
```

ENHANCED EXECUTION FLOW:
1. Execute each action (click, type, navigate)
2. ALWAYS use browser_snapshot after each action to capture page state
3. IF the step has an expected result: Analyze snapshot and verify if expectation is met
4. IF no expected result: Just capture snapshot for logging
5. Continue to next step

Always provide detailed technical information about:
- CSS selectors used
- Actions performed 
- Values entered
- Page state captured in snapshots
- Verification results (when expected results exist)

Continue until all test steps are completed or you encounter an error."""

    conversation_history = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": test_prompt}
    ]
    
    execution_log = []
    max_iterations = 25
    iteration = 0

    print("🧪 Starting AI-driven test execution with conditional verification...")

    while iteration < max_iterations:
        iteration += 1
        print(f"--- Iteration {iteration} ---")

        try:
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

            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                messages=conversation_history,
                tools=tools,
                tool_choice="auto",
                temperature=0
            )

            message = response.choices[0].message

            conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls if message.tool_calls else None
            })

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except:
                        args = {}
                    
                    result = await manager.execute_tool(tool_name, args)
                    
                    # Enhanced logging with verification tracking
                    log_entry = {
                        "tool": tool_name,
                        "args": args,
                        "description": f"{tool_name} called with arguments {args}",
                        "is_verification": tool_name == "browser_snapshot"
                    }

                    # Only include result for non-snapshot tools to save tokens
                    if tool_name != "browser_snapshot":
                        log_entry["result"] = result.get("result", {})

                    execution_log.append(log_entry)

                    conversation_history.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })
                continue
            else:
                print(f"🤖 AI completed: {message.content}")
                break

        except Exception as e:
            print(f"❌ Error in iteration {iteration}: {e}")
            break

    print(f"✅ Test execution completed after {iteration} iterations")
    return execution_log