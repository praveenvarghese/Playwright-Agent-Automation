#!/usr/bin/env python3
"""
Complete Playwright Test Generator - Single File
All functionality inlined - no dependencies on other runner files
"""

import asyncio
import json
import os
import sys
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import only the modules that still exist
from playwright_generation.common.vector_retrieval import fetch_test_case_by_id
from playwright_generation.mcp_helpers.mcp_manager import WorkingMCPManager
from playwright_generation.agents.agent_config import create_agents
from playwright_generation.orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized, load_mcp_execution_log
from playwright_generation.common.azure_devops_client import fetch_from_azure_devops
# =============================================================================
# STATE DEFINITION (from pom_test_runner.py)
# =============================================================================

class TestGenerationState(TypedDict):
    test_case_id: str
    test_case: dict
    selectors: list
    messages: List[BaseMessage]
    page_objects: list
    test_file: str

# =============================================================================
# MCP AUTOMATION FUNCTIONS (from mcp_test_generator.py)
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
        
        execution_log = await execute_with_conversation(manager, test_case_id, test_case)
        
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

async def execute_with_conversation(manager, test_case_id, test_case):
    """Execute test using AI conversation"""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview"
    )
    
    test_prompt = f"""
Execute this test case step by step:

CONTEXT:
- Application URL: {os.getenv('APP_URL')}
- Username: {os.getenv('APP_USERNAME')}
- Password: {os.getenv('APP_PASSWORD')}

🚨 CRITICAL: Use Playwright locator methods for all interactions:
- Use getByRole, getByText, getByLabel methods
- Look at the page snapshot to identify the correct element names

PREREQUISITE STEPS:
1. Navigate to the application URL
2. Wait for page to load
3. Look for login form elements using CSS selectors (input[name="username"], etc.)
4. Fill in username with the provided credentials
5. Fill in password and submit

TEST STEPS:
{test_case.get('steps', '')}

EXPECTED RESULTS:
{test_case.get('expectedResults', '')}

Continue until all test steps are completed or you encounter an error.
"""

    system_msg = """You are executing a test case using Playwright MCP tools. 
    Execute ALL steps in the test case, one by one. After each tool call result, 
    continue with the next step until the entire test is complete.
    
    Always provide detailed technical information about:
    - CSS selectors used
    - Actions performed 
    - Values entered
    - Results observed
    
    Continue until all test steps are completed or you encounter an error."""

    conversation_history = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": test_prompt}
    ]
    
    execution_log = []
    max_iterations = 20
    iteration = 0

    print("🧪 Starting AI-driven test execution...")

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
                    
                    log_entry = {
                        "tool": tool_name,
                        "args": args,
                        "result": result.get("result", {}),
                        "description": f"{tool_name} called with arguments {args}"
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

def extract_selectors(execution_log):
    """Extract selectors from MCP execution log"""
    selectors = []
    
    for entry in execution_log:
        tool = entry["tool"]
        args = entry["args"]
        result = entry.get("result", {})
        
        if tool == "browser_navigate":
            selectors.append({
                "action": "navigate", 
                "url": args.get('url', '')
            })
            
        elif tool in ["browser_type", "browser_click"]:
            playwright_code = extract_playwright_code(result)
            
            if playwright_code:
                parsed_action = llm_parse_action(tool, playwright_code, args)
                if parsed_action:
                    selectors.append(parsed_action)
                else:
                    # Fallback
                    selectors.append({
                        "action": "input" if tool == "browser_type" else "click",
                        "rawSelector": playwright_code,
                        "elementName": args.get("element", ""),
                        "value": args.get("text", "") if tool == "browser_type" else None
                    })
    
    return selectors

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
# 6-STEP WORKFLOW (from pom_test_runner.py) 
# =============================================================================

def create_pom_test_workflow():
    """Create the 6-step LangGraph workflow"""
    agents = create_agents()
    
    def generate_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 1: Generating Page Object Models")
        
        selectors_json = json.dumps(state["selectors"], indent=2)
        test_case = state["test_case"]
        
        initial_message = HumanMessage(
            content=f"""
Generate Page Object Models for Playwright based on the provided selectors. 

Test Case ID: {state["test_case_id"]}
Test Case Title: {test_case.get('title', '')}

MCP Execution Log (contains actual working Playwright code):
```json
{selectors_json}
```

Instructions:
1. Analyze the selectors to identify logical pages
2. Create specific page objects for each logical page
3. Follow Page Object Model best practices
4. Format your response with clear file headers and JavaScript code blocks

Format each file as:
### 1. FileName.js
```javascript
// Implementation
```
""",
            name="User"
        )
        
        current_messages = state.get("messages", []) + [initial_message]
        response = agents["pom_generator_v2"](current_messages)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def critique_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 2: Critiquing Page Object Models")
        
        critique_request = HumanMessage(
            content="""
Review the Page Object Models generated above and suggest improvements.

Focus on:
1. Structure and organization
2. Selector strategies
3. Method design and naming
4. Error handling
5. Documentation

Provide specific code examples for your suggestions.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [critique_request]
        response = agents["pom_critic_v2"](current_messages)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def improve_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 3: Improving Page Object Models")
        
        improvement_request = HumanMessage(
            content="""
Based on the critique provided above, please improve the Page Object Models.
Address the specific issues mentioned in the critique while maintaining the same format:

### 1. FileName.js
```javascript
// Improved Implementation
```

Focus on implementing the suggestions from the critique.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [improvement_request]
        response = agents["pom_generator_v2"](current_messages)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def generate_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 4: Generating Test Script")
        
        test_case_json = json.dumps(state["test_case"], indent=2)
        
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
        
        test_request = HumanMessage(
            content=f"""
    Create a Playwright test script using the Page Object Models provided in this conversation.

    IMPORTANT: First extract ALL method names from the Page Object classes below, then use ONLY those exact method names.

    Page Object Models (Latest Version):
    {improved_poms}

    Test Case:
    ```json
    {test_case_json}
    ```

    Requirements:
    1. Extract method names from POMs above - use ONLY those exact names
    2. Do NOT use any hardcoded values. Use fields from `testCase`
    3. Follow best practices: Arrange → Act → Assert
    4. Use ES6 module imports
    5. NO try-catch blocks unless handling specific expected errors
    6. NO unnecessary waits or complexity

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
Review the test script generated above and suggest improvements.

MCP Execution Log:
```json
{json.dumps(mcp_log, indent=2) if mcp_log else "No MCP log found"}
```

Focus on:
1. Replace placeholder selectors with real ones from MCP log
2. Replace fake success messages with real verification from MCP final state
3. Reliability and robustness
4. Wait strategies
5. Assertion quality
6. Error handling
7. Test structure
8. Proper use of Page Object Models
9. Adherence to the testCase value requirements

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
    """Save page objects to files"""
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = []
    for i, code_block in enumerate(page_objects):
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
# MAIN EXECUTION FUNCTIONS
# =============================================================================

async def generate_complete_test(test_case_id: str, output_dir: str = "complete_tests"):
    """Complete test generation workflow"""
    
    print(f"🚀 Generating complete test for {test_case_id}")
    
    # Step 1: Get test case from Azure
    print("📚 Fetching test case...")
    test_case = await fetch_test_case(test_case_id)
    if not test_case:
        print("❌ Test case not found")
        return False
    print(f"✅ Found: {test_case.get('title', 'Unknown')}")
    test_case_id = test_case['id']
    
    # Step 2: Run MCP automation  
    print("🎭 Running MCP automation...")
    execution_log = await run_mcp_automation(test_case_id, test_case)
    if not execution_log:
        print("❌ MCP automation failed")
        return False
    print("✅ MCP automation completed")
        
    # Step 3: Extract selectors from execution log
    print("🔍 Extracting selectors...")
    selectors = extract_selectors(execution_log)
    if not selectors:
        print("❌ No selectors extracted")
        return False
    print(f"✅ Extracted {len(selectors)} selectors")
    
    # Save selectors to file
    with open(f"{test_case_id}_selectors.json", "w") as f:
        json.dump(selectors, f, indent=2)
        
    # Step 4: Run 6-step POM/Test generation workflow
    print("⚙️ Running 6-step generation workflow...")
    success = await run_workflow(test_case_id, test_case, selectors, output_dir)
    
    if success:
        print(f"🎉 Complete test generation successful!")
        print(f"📁 Files saved in {output_dir}")
    else:
        print("❌ Workflow failed")
    
    return success

async def run_workflow(test_case_id, test_case, selectors, output_dir):
    """Run the 6-step generation workflow"""
    
    try:
        # Create workflow
        workflow = create_pom_test_workflow()
        
        # Define initial state
        initial_state = {
            "test_case_id": test_case_id,
            "test_case": test_case,
            "selectors": selectors,
            "messages": [],
            "page_objects": [],
            "test_file": ""
        }
        
        # Run workflow
        print("▶️ Running 6-step workflow...")
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
            print(f"✅ Generated {len(page_objects)} page object files")
        
        if test_file:
            save_test_script(test_file, tests_dir, test_case_id)
            print(f"✅ Generated test file")
        
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
        return
        
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "complete_tests"
    
    setup_environment()
    
    success = await generate_complete_test(test_case_id, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())