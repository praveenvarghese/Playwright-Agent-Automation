#!/usr/bin/env python3
"""
Enhanced Playwright Test Generator with Conditional Verification
Now includes verification only when Azure DevOps steps have expected results
"""

import asyncio
import json
import os
import sys
from urllib import response
import warnings
import re
from typing import TypedDict, List
from dotenv import load_dotenv
from openai import AzureOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# Suppress warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed transport.*")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

# Add project to path  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import only the modules that still exist
from common.vector_retrieval import fetch_test_case_by_id
from mcp_helpers.mcp_manager import WorkingMCPManager
from agents.agent_config import create_agents
from orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized, load_mcp_execution_log
from common.azure_devops_client import fetch_from_azure_devops

# =============================================================================
# STATE DEFINITION
# =============================================================================

class TestGenerationState(TypedDict):
    test_case_id: str
    test_case: dict
    messages: List[BaseMessage]
    page_objects: list
    test_file: str

# =============================================================================
# MCP AUTOMATION FUNCTIONS - ENHANCED WITH CONDITIONAL VERIFICATION
# =============================================================================

async def fetch_test_case(test_case_id):
    """Fetch test case from configured source (vector/file/azure_devops)"""
    source = os.getenv("TEST_CASE_SOURCE", "vector").lower()
    
    if source == "azure_devops":
        print(f"📄 Loading test case from Azure DevOps: {test_case_id}")
        try:
            return await fetch_from_azure_devops(test_case_id)
        except Exception as e:
            print(f"❌ Error loading from Azure DevOps: {e}")
            return None
    
    elif source == "file":
        print(f"📄 Loading test case from file: {test_case_id}")
        try:
            with open(test_case_id, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            test_case = {
                'id': 'TC-FILE-001',
                'title': '',
                'steps': '',
                'expectedResults': ''
            }
            
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == 'id':
                        test_case['id'] = value
                    elif key == 'title':
                        test_case['title'] = value
                        current_section = None
                    elif key == 'steps':
                        current_section = 'steps'
                        test_case['steps'] = value if value else ''
                    elif key == 'expected':
                        current_section = 'expectedResults'
                        test_case['expectedResults'] = value if value else ''
                elif current_section and line:
                    if test_case[current_section]:
                        test_case[current_section] += '\n' + line
                    else:
                        test_case[current_section] = line
            
            print(f"✅ Loaded from file: {test_case.get('title', 'Unknown')}")
            return test_case
            
        except FileNotFoundError:
            print(f"❌ File not found: {test_case_id}")
            return None
        except Exception as e:
            print(f"❌ Error loading file: {e}")
            return None
    
    else:  # vector (default)
        try:
            print(f"🔍 Searching for test case ID: {test_case_id}")
            test_case = await fetch_test_case_by_id(test_case_id)
            if test_case:
                print(f"✅ Found: {test_case.get('title', 'Unknown')}")
            return test_case
        except Exception as e:
            print(f"❌ Azure Search error: {str(e)}")
            return None
        
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
    """
    ENHANCED: Execute test with conditional verification based on Azure DevOps expected results
    """
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview"
    )
    
    # 🎯 ENHANCED: Check for structured steps with expected results
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
    max_iterations = 25  # Increased for verification steps
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
                        "result": result.get("result", {}),
                        "description": f"{tool_name} called with arguments {args}",
                        "is_verification": tool_name == "browser_snapshot"
                    }
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

def extract_playwright_code(result):
    """Extract Playwright locator from MCP result"""
    try:
        if not isinstance(result, dict) or "content" not in result:
            return None
            
        for content_item in result["content"]:
            if isinstance(content_item, dict) and "text" in content_item:
                text = content_item["text"]
                
                lines = text.split('\n')
                for line in lines:
                    clean_line = line.strip()
                    if clean_line.startswith('await page.'):
                        pattern = r"await page\.(getBy\w+\([^)]+\))\.(\w+)\("
                        match = re.search(pattern, clean_line)
                        
                        if match:
                            return match.group(1)
                        return clean_line
                        
    except Exception:
        pass
        
    return None

def llm_parse_action(tool, playwright_code, args):
    """Use LLM to parse Playwright selector into clean format"""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    )
    
    prompt = f"""
You are an expert at extracting UI actions and selectors from Playwright automation logs.

Given:
- Tool: {tool}
- Playwright code: {playwright_code}
- Args: {json.dumps(args)}

Output ONLY the JSON object with these required fields:
1. "action": "input" or "click"
2. "target": object describing the selector
3. "rawSelector": the exact Playwright locator string
4. "elementName": human readable name
5. "value": for input actions only

Example:
{{
  "action": "input",
  "target": {{ "type": "role", "role": "textbox", "name": "Username" }},
  "value": "admin",
  "rawSelector": "getByRole('textbox', {{ name: 'Username' }})",
  "elementName": "Username input"
}}
"""
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content.strip()
        parsed_result = json.loads(result_text)
        
        if tool == "browser_type" and "value" not in parsed_result:
            parsed_result["value"] = args.get("text", "")
        
        return parsed_result
        
    except Exception:
        return None

# =============================================================================
# 6-STEP WORKFLOW (ENHANCED FOR VERIFICATION DATA)
# =============================================================================

def create_pom_test_workflow():
    """Create the 6-step LangGraph workflow with verification enhancement"""
    agents = create_agents()
    
    def generate_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 1: Generating Page Object Models with Verification Methods")
        
        # Load the FULL execution log with verification data
        execution_log = load_mcp_execution_log(state["test_case_id"])
        execution_json = json.dumps(execution_log, indent=2) if execution_log else "No MCP execution log available"
        test_case = state["test_case"]
        
        # Extract structured steps for context
        structured_steps = test_case.get("structured_steps", [])
        structured_steps_json = json.dumps(structured_steps, indent=2) if structured_steps else "No structured steps available"
        
        initial_message = HumanMessage(
            content=f"""
Generate Page Object Models for Playwright based on the execution log with verification data.

Test Case ID: {state["test_case_id"]}
Test Case Title: {test_case.get('title', '')}

Structured Steps with Expected Results:
```json
{structured_steps_json}
```

MCP Execution Log (contains actions AND verification snapshots):
```json
{execution_json}
```

ENHANCED INSTRUCTIONS:
1. Analyze both actions and verification results in the log
2. Create verification methods for steps that had expected results
3. Use snapshot data to understand what assertions are needed
4. Generate both action methods AND verification methods

Example verification method based on expected results:
```javascript
async verifyEditDialogVisible() {{
  await expect(this.page.getByRole('dialog')).toBeVisible();
  await expect(this.page.getByText('Edit environment')).toBeVisible();
}}

async verifyEnvironmentHasLinkedTag() {{
  await expect(this.page.getByText('Linked')).toBeVisible();
}}
```

Format each file as:
### 1. FileName.js
```javascript
// Implementation with both action and verification methods
```
""",
            name="User"
        )
        
        current_messages = state.get("messages", []) + [initial_message]
        response = agents["pom_generator_v2"](current_messages)
        with open(f"{state['test_case_id']}_pom_step1_generate.txt", "w", encoding='utf-8') as f:
            f.write(response.content)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def critique_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 2: Critiquing Page Object Models")
        
        execution_log = load_mcp_execution_log(state["test_case_id"])
        execution_json = json.dumps(execution_log, indent=2) if execution_log else "No MCP execution log available"
        critique_request = HumanMessage(
        content=f"""
Review the Page Object Models generated above, focusing on page separation and URL boundaries.

MCP Execution Log (for URL path analysis):
```json
{execution_json}

Focus on:
1. Do verification methods match the expected results from the test case?
2. Are assertions realistic based on the snapshot data?
3. Structure and organization
4. Selector strategies
5. Method design and naming
6. Error handling
7. CRITICAL: Are actions from different URL paths mixed in the same page class?

Provide specific code examples for your suggestions.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [critique_request]
        response = agents["pom_critic_v2"](current_messages)
        with open(f"{state['test_case_id']}_pom_step2_critique.txt", "w", encoding='utf-8') as f:
            f.write(response.content)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def improve_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 3: Improving Page Object Models")
        
        improvement_request = HumanMessage(
            content="""
Based on the critique provided above, please improve the Page Object Models.
Address the specific issues mentioned while maintaining the same format:

### 1. FileName.js
```javascript
// Improved Implementation with enhanced verification methods
```

Focus on implementing the suggestions from the critique, especially around verification methods.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [improvement_request]
        response = agents["pom_generator_v2"](current_messages)
        print(f"DEBUG: Response content for extraction: {response.content[:500]}...")
        with open(f"{state['test_case_id']}_pom_step3_improve.txt", "w", encoding='utf-8') as f:
            f.write(response.content)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def generate_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 4: Generating Test Script with Real Assertions")
        
        test_case_json = json.dumps(state["test_case"], indent=2)
        
        # Extract structured steps for better assertions
        structured_steps = state["test_case"].get("structured_steps", [])
        
        # Extract improved POMs from conversation
        improved_poms = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, 'name') and msg.name == "POM_Generator" and "improved" in msg.content.lower():
                improved_poms = msg.content
                break
        
        # If no improved POMs found, use the latest POM response
        if not improved_poms:
            for msg in reversed(state["messages"]):
                if hasattr(msg, 'name') and msg.name == "POM_Generator":
                    improved_poms = msg.content
                    break
        
        # Load MCP execution log
        mcp_log = load_mcp_execution_log(state["test_case_id"])
        
        test_request = HumanMessage(
            content=f"""
Create a Playwright test script using the Page Object Models.

Page Object Models:
{improved_poms}

MCP EXECUTION LOG (FOLLOW THIS EXACTLY - this is what actually worked):
```json
{json.dumps(mcp_log, indent=2)}
```

Test Case Context (for understanding purpose only):
```json
{test_case_json}
```

CRITICAL: Follow the MCP execution log sequence exactly. Use real values from the MCP log, not the test case description.

REQUIREMENTS:
1. Extract method names from POMs above - use ONLY those exact names
2. Follow the MCP log sequence exactly
3. Use actual values from MCP log (URLs, usernames, element names)
4. Include login sequence from MCP log
5. Use verification methods when MCP log shows verification snapshots
6. Use ES6 module imports
7. Create testCase object with real data from MCP log

Format the output as:
### N. testCase.spec.js
```javascript
// Implementation here
```
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_request]
        response = agents["test_generator_v2"](current_messages)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def critique_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 5: Critiquing Test Script")
        
        mcp_log = load_mcp_execution_log(state["test_case_id"])
        
        test_critique_request = HumanMessage(
            content=f"""
Review the test script generated above, focusing on verification usage.

MCP Execution Log with Verification Data:
```json
{json.dumps(mcp_log, indent=2) if mcp_log else "No MCP log found"}
```

Focus on:
1. Are verification methods called for steps that had expected results?
2. Are the right verification methods used based on MCP snapshot data?
3. Test structure and flow
4. Proper use of Page Object Models
5. Assertion quality and coverage
6. Adherence to the testCase value requirements

Provide specific code examples for your suggestions.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_critique_request]
        response = agents["test_critic_v2"](current_messages)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def improve_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 6: Improving Test Script")
        
        test_improvement_request = HumanMessage(
            content="""
Based on the test critique provided above, please improve the test script.
Address the specific issues mentioned while maintaining compatibility with the Page Object Models.

Ensure verification methods are used appropriately for steps with expected results.

Provide the complete improved implementation as:
### N. testCase.spec.js
```javascript
// Improved Implementation
```

Ensure all critique points are addressed and the test follows best practices.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_improvement_request]
        response = agents["test_generator_v2"](current_messages)
        updated_messages = current_messages + [response]
        
        # Extract final outputs
        page_objects = extract_page_objects_from_specialized(state["messages"][-4].content)  # From improved POM step
        test_file = extract_test_script_from_specialized(response.content)
        
        # Try fallback extraction if needed
        if not test_file:
            test_file = extract_test_script_from_specialized(state.get("messages", [])[-2].content if len(state.get("messages", [])) > 1 else "")
        
        # More flexible extraction if still no test file
        if not test_file:
            flexible_matches = re.findall(r'### \d+\. \w+\.spec\.js.*?```javascript\s+(.*?)```', response.content, re.DOTALL)
            if flexible_matches:
                test_file = flexible_matches[0].strip()
        
        return {
            **state, 
            "messages": updated_messages,
            "page_objects": page_objects,
            "test_file": test_file
        }

    # Build workflow
    workflow = StateGraph(TestGenerationState)
    
    workflow.add_node("generate_pom", generate_pom_node)
    workflow.add_node("critique_pom", critique_pom_node)
    workflow.add_node("improve_pom", improve_pom_node)
    workflow.add_node("generate_test", generate_test_node)
    workflow.add_node("critique_test", critique_test_node)
    workflow.add_node("improve_test", improve_test_node)
    
    workflow.add_edge("generate_pom", "critique_pom")
    workflow.add_edge("critique_pom", "improve_pom")
    workflow.add_edge("improve_pom", "generate_test")
    workflow.add_edge("generate_test", "critique_test")
    workflow.add_edge("critique_test", "improve_test")
    workflow.add_edge("improve_test", END)
    
    workflow.set_entry_point("generate_pom")
    
    return workflow.compile()

def save_page_objects(page_objects, output_dir):
    """Save page objects to files - extract class names from JSON content."""
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = []
    for i, code_block in enumerate(page_objects):
        # Extract class name from the actual code content
        match = re.search(r'export class\s+(\w+)', code_block)
        if match:
            filename = f"{match.group(1)}.js"
        else:
            filename = f"PageObject_{i+1}.js"
        
        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code_block)
        
        saved_files.append(file_path)
        print(f"✅ Saved: {file_path}")
    
    return saved_files

def save_test_script(test_content, output_dir, test_case_id):
    """Save test script to file"""
    os.makedirs(output_dir, exist_ok=True)
    
    test_file_path = os.path.join(output_dir, f"{test_case_id}.spec.js")
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"✅ Saved test: {test_file_path}")
    return test_file_path

# =============================================================================
# MAIN EXECUTION FUNCTIONS (ENHANCED)
# =============================================================================

async def generate_complete_test(test_case_id: str, output_dir: str = "complete_tests"):
    """Complete test generation workflow with conditional verification"""
    
    print(f"🚀 Generating complete test with conditional verification for {test_case_id}")
    
    # Step 1: Get test case from configured source
    print("📚 Fetching test case...")
    test_case = await fetch_test_case(test_case_id)
    if not test_case:
        print("❌ Test case not found")
        return False
    print(f"✅ Found: {test_case.get('title', 'Unknown')}")
    test_case_id = test_case['id']
    
    # Show structured steps info
    structured_steps = test_case.get('structured_steps', [])
    if structured_steps:
        steps_with_expected = [s for s in structured_steps if s.get('expected')]
        print(f"📋 Found {len(structured_steps)} total steps, {len(steps_with_expected)} with expected results")
    
    # Step 2: Run MCP automation with conditional verification
    print("🎭 Running MCP automation with conditional verification...")
    execution_log = await run_mcp_automation(test_case_id, test_case)
    if not execution_log:
        print("❌ MCP automation failed")
        return False
    print("✅ MCP automation completed with verification data")
        
    # Step 4: Run 6-step POM/Test generation workflow
    print("⚙️ Running enhanced 6-step generation workflow...")
    success = await run_workflow(test_case_id, test_case, output_dir)
    
    if success:
        print(f"🎉 Complete test generation successful with verification methods!")
        print(f"📁 Files saved in {output_dir}")
    else:
        print("❌ Workflow failed")
    
    return success

async def run_workflow(test_case_id, test_case, output_dir):
    """Run the enhanced 6-step generation workflow"""
    
    try:
        # Create workflow
        workflow = create_pom_test_workflow()
        
        # Define initial state
        initial_state = {
            "test_case_id": test_case_id,
            "test_case": test_case,
            "messages": [],
            "page_objects": [],
            "test_file": ""
        }
        
        # Run workflow
        print("▶️ Running enhanced 6-step workflow...")
        final_state = workflow.invoke(initial_state)
        
        # Extract results
        page_objects = final_state.get("page_objects", [])
        test_file = final_state.get("test_file", "")
        
        # If no results, try extracting from messages
        if not page_objects and final_state.get("messages"):
            # Find improved POM response
            for msg in final_state["messages"]:
                if hasattr(msg, 'name') and 'POM' in str(msg.name):
                    page_objects = extract_page_objects_from_specialized(msg.content)
                    if page_objects:
                        break
        
        if not test_file and final_state.get("messages"):
            # Find test response  
            for msg in reversed(final_state["messages"]):
                if hasattr(msg, 'name') and 'Test' in str(msg.name):
                    test_file = extract_test_script_from_specialized(msg.content)
                    if test_file:
                        break
        
        # Save results
        pages_dir = os.path.join(output_dir, "pages")
        tests_dir = os.path.join(output_dir, "tests")
        
        if page_objects:
            save_page_objects(page_objects, pages_dir)
            print(f"✅ Generated {len(page_objects)} page object files with verification methods")
        
        if test_file:
            save_test_script(test_file, tests_dir, test_case_id)
            print(f"✅ Generated test file with verification calls")
        
        return bool(page_objects and test_file)
        
    except Exception as e:
        print(f"❌ Workflow error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def setup_environment():
    """Validate required environment variables"""
    required_vars = [
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", 
        "AZURE_OPENAI_DEPLOYMENT_NAME", "APP_URL", "APP_USERNAME", "APP_PASSWORD"
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python mcp_test_generator_simple.py <TEST_CASE_ID> [output_dir]")
        print("Example: python mcp_test_generator_simple.py TC-ENV-001")
        print("Example: python mcp_test_generator_simple.py TestCaseFile.txt")
        print("Example: python mcp_test_generator_simple.py 12345  # Azure DevOps work item")
        return
        
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "complete_tests"
    
    setup_environment()
    
    success = await generate_complete_test(test_case_id, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())