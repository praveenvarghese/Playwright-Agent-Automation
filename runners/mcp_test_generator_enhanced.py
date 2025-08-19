#!/usr/bin/env python3
"""
Complete Playwright Test Generator - Intelligence Enhanced Version
Integrates Project Intelligence Scanner with existing MCP-based test generation
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

# Add project to path - fix for running from different directories
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# Import modules - using relative imports and sys.path
try:
    from common.vector_retrieval import fetch_test_case_by_id
    from mcp_helpers.mcp_manager import WorkingMCPManager
    from agents.agent_config import create_agents
    from orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized, load_mcp_execution_log
    from common.azure_devops_client import fetch_from_azure_devops
except ImportError:
    # Fallback for when running from project root
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    selectors: list
    messages: List[BaseMessage]
    page_objects: list
    test_file: str
    intelligence_decisions: dict

# =============================================================================
# MCP AUTOMATION FUNCTIONS
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

async def run_intelligence_analysis(test_case, target_project_path):
    """Run intelligence analysis on target project"""
    if not target_project_path or not os.path.exists(target_project_path):
        print("⚠️ No target project path provided or path doesn't exist")
        return None
    
    try:
        print("🧠 Running intelligence analysis...")
        try:
            from intelligence.project_intelligence import create_project_intelligence
        except ImportError:
            from intelligence.project_intelligence import create_project_intelligence
        
        intelligence = create_project_intelligence(target_project_path)
        analysis = intelligence.analyze_project_structure()
        decisions = intelligence.make_integration_decisions(test_case)
        
        print(f"✅ Intelligence analysis complete")
        print(f"📊 Found {len(analysis.get('pages', {}).get('classes', []))} existing page classes")
        print(f"📊 Found {len(analysis.get('tests', {}).get('files', []))} existing test files")
        
        return {
            'analysis': analysis,
            'decisions': decisions
        }
        
    except Exception as e:
        print(f"⚠️ Intelligence analysis failed: {e}")
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
# ENHANCED 6-STEP WORKFLOW WITH INTELLIGENCE
# =============================================================================

def create_intelligence_enhanced_workflow():
    """Create the enhanced 6-step LangGraph workflow with intelligence context"""
    agents = create_agents()
    
    def generate_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 1: Generating Page Object Models")
        
        selectors_json = json.dumps(state["selectors"], indent=2)
        test_case = state["test_case"]
        
        # Build intelligence context
        intelligence_context = ""
        if state.get("intelligence_decisions"):
            decisions = state["intelligence_decisions"]
            page_decision = decisions.get('page_decision', {})
            method_reuse = decisions.get('method_reuse', [])
            patterns = decisions.get('patterns', {})
            
            intelligence_context = f"""
EXISTING PROJECT CONTEXT:
- Page Decision: {page_decision.get('action', 'create').upper()} {page_decision.get('target', 'NewPage')}
- Reusable Methods: {', '.join(method_reuse) if method_reuse else 'None detected'}
- Naming Convention: {patterns.get('naming_convention', {}).get('page_classes', 'Unknown')}

INTEGRATION GUIDANCE:
- Action: {page_decision.get('action', 'create').upper()} page object
- Target: {page_decision.get('target', 'NewPage')}
- Reuse existing methods where applicable
- Follow detected project naming conventions
"""
        
        initial_message = HumanMessage(
            content=f"""
Generate Page Object Models for Playwright based on the provided selectors.

{intelligence_context}

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
4. If extending existing classes, focus only on NEW methods needed
5. Format your response with clear file headers and JavaScript code blocks

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
        
        # Include intelligence context in critique
        intelligence_context = ""
        if state.get("intelligence_decisions"):
            decisions = state["intelligence_decisions"]
            intelligence_context = f"""
Consider the intelligence analysis when reviewing:
- Existing project has {len(decisions.get('analysis', {}).get('pages', {}).get('classes', []))} page classes
- Integration approach: {decisions.get('page_decision', {}).get('action', 'create')}
- Detected patterns: {decisions.get('patterns', {})}
"""
        
        critique_request = HumanMessage(
            content=f"""
Review the Page Object Models generated above and suggest improvements.

{intelligence_context}

Focus on:
1. Structure and organization
2. Selector strategies
3. Method design and naming
4. Error handling
5. Documentation
6. Integration with existing project patterns

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
        
        # Build intelligence context for test generation
        intelligence_context = ""
        if state.get("intelligence_decisions"):
            decisions = state["intelligence_decisions"]
            method_reuse = decisions.get('method_reuse', [])
            analysis = decisions.get('analysis', {})
            patterns = decisions.get('patterns', {})
            
            # Get existing test patterns generically
            existing_tests = analysis.get('tests', {}).get('files', [])
            test_patterns = []
            if existing_tests:
                for test in existing_tests[:3]:  # Show sample patterns
                    test_patterns.append(f"- {test.get('name', 'unknown')}: {len(test.get('test_cases', []))} tests")
            
            intelligence_context = f"""
EXISTING PROJECT CONTEXT FOR TEST GENERATION:
- Strategy: CREATE new test file (follow existing patterns)
- Reusable Methods Available: {', '.join(method_reuse) if method_reuse else 'None detected'}
- Existing Test Patterns Found:
{chr(10).join(test_patterns) if test_patterns else '  - No existing patterns detected'}
- Naming Convention: {patterns.get('naming_convention', {}).get('test_files', 'Follow standard conventions')}
- Test Structure: {patterns.get('test_structure', {}).get('uses_describe', 'Standard structure')}

INTEGRATION GUIDANCE:
- Create NEW test file with unique name
- Use existing methods where available: {method_reuse}
- Follow the patterns observed in existing tests
- Structure similar to detected project conventions
"""
        
        test_request = HumanMessage(
            content=f"""
Create a Playwright test script using the improved Page Object Models from above.

{intelligence_context}

You must use the following testCase values inside your actual test code.

✅ Correct:
    await page.goto(testCase.loginUrl);
    await loginPage.login(testCase.username, testCase.password);
    await targetPage.performAction(testCase.inputValue);

❌ Incorrect:
    await page.goto('https://example.com/login');
    await loginPage.login('admin', 'password');

Test Case:
```json
{test_case_json}
```

Requirements:
1. Do NOT use any hardcoded values. Use fields from `testCase`
2. Use only the values passed in `testCase` for all navigation, inputs, and assertions
3. Follow best practices: Arrange → Act → Assert
4. Use ES6 module imports
5. Reuse existing methods where indicated by intelligence context

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
        
        # Include intelligence context in test critique
        intelligence_context = ""
        if state.get("intelligence_decisions"):
            decisions = state["intelligence_decisions"]
            intelligence_context = f"""
Consider intelligence analysis in critique:
- Existing test files: {len(decisions.get('analysis', {}).get('tests', {}).get('files', []))}
- Integration approach: CREATE new test file
- Method reuse opportunities: {decisions.get('method_reuse', [])}
"""
        
        test_critique_request = HumanMessage(
            content=f"""
Review the test script generated above and suggest improvements.

{intelligence_context}

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
10. Integration with existing project patterns

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

# =============================================================================
# SMART FILE OPERATIONS
# =============================================================================

def smart_file_operations(page_objects, test_file, test_case_id, output_dir, intelligence_decisions):
    """Handle file operations based on intelligence decisions"""
    
    if not intelligence_decisions:
        print("📁 Using traditional file operations (no intelligence)")
        # Fallback to traditional approach
        pages_dir = os.path.join(output_dir, "pages")
        tests_dir = os.path.join(output_dir, "tests")
        save_page_objects(page_objects, pages_dir)
        save_test_script(test_file, tests_dir, test_case_id)
        return
    
    print("🧠 Using intelligent file operations")
    
    # Smart page object operations
    page_decision = intelligence_decisions.get('page_decision', {})
    if page_decision.get('action') == 'extend':
        extend_existing_page_objects(page_objects, page_decision.get('target'), output_dir)
    else:
        pages_dir = os.path.join(output_dir, "pages")
        save_page_objects(page_objects, pages_dir)
    
    # Always create new test files (no appending)
    tests_dir = os.path.join(output_dir, "tests")
    save_test_script(test_file, tests_dir, test_case_id)
    print(f"✅ Created new test file following detected project patterns")

def extend_existing_page_objects(new_page_objects, target_class, output_dir):
    """Extend existing page object class with new methods"""
    print(f"🔧 Extending {target_class} with new methods")
    
    # This is a placeholder for the actual implementation
    # Would need to:
    # 1. Find the existing page object file
    # 2. Parse it to find the class
    # 3. Add new methods to the class
    # 4. Write back to file
    
    # For now, fall back to creating new files
    pages_dir = os.path.join(output_dir, "pages")
    save_page_objects(new_page_objects, pages_dir)
    print(f"⚠️ Extend functionality not fully implemented, created new files instead")

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
    if not test_content:
        print(f"⚠️ Warning: Empty test content for {test_case_id}")
        return None
        
    os.makedirs(output_dir, exist_ok=True)
    
    test_file_path = os.path.join(output_dir, f"{test_case_id}.spec.js")
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"✅ Saved test: {test_file_path}")
    return test_file_path

# =============================================================================
# MAIN EXECUTION FUNCTIONS
# =============================================================================

async def generate_complete_test(test_case_id: str, output_dir: str = "complete_tests", target_project_path: str = None):
    """Complete test generation workflow with intelligence enhancement"""
    
    print(f"🚀 Generating complete test for {test_case_id}")
    
    # Step 1: Get test case from source
    print("📚 Fetching test case...")
    test_case = await fetch_test_case(test_case_id)
    if not test_case:
        print("❌ Test case not found")
        return False
    print(f"✅ Found: {test_case.get('title', 'Unknown')}")
    test_case_id = test_case['id']
    
    # Step 1.5: Intelligence Analysis (if target project provided)
    intelligence_results = None
    if target_project_path:
        intelligence_results = await run_intelligence_analysis(test_case, target_project_path)
    
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
        
    # Step 4: Run enhanced 6-step generation workflow
    print("⚙️ Running enhanced 6-step generation workflow...")
    success = await run_enhanced_workflow(
        test_case_id, 
        test_case, 
        selectors, 
        output_dir, 
        intelligence_results.get('decisions') if intelligence_results else None
    )
    
    if success:
        print(f"🎉 Complete test generation successful!")
        print(f"📁 Files saved in {output_dir}")
        
        # Print intelligence insights if available
        if intelligence_results:
            decisions = intelligence_results.get('decisions', {})
            print(f"🧠 Intelligence insights:")
            print(f"   Page strategy: {decisions.get('page_decision', {})}")
            print(f"   Test strategy: Always create new test file")
            print(f"   Reusable methods: {len(decisions.get('method_reuse', []))} found")
    else:
        print("❌ Workflow failed")
    
    return success

async def run_enhanced_workflow(test_case_id, test_case, selectors, output_dir, intelligence_decisions):
    """Run the enhanced 6-step generation workflow with intelligence context"""
    
    try:
        # Create enhanced workflow
        workflow = create_intelligence_enhanced_workflow()
        
        # Define initial state with intelligence decisions
        initial_state = {
            "test_case_id": test_case_id,
            "test_case": test_case,
            "selectors": selectors,
            "messages": [],
            "page_objects": [],
            "test_file": "",
            "intelligence_decisions": intelligence_decisions
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
            # Find test response with better debugging
            for i, msg in enumerate(reversed(final_state["messages"])):
                if hasattr(msg, 'name') and 'Test' in str(msg.name):
                    print(f"🔍 Debug: Found test message {i}: {msg.name}")
                    print(f"🔍 Debug: Message content preview: {str(msg.content)[:200]}...")
                    test_file = extract_test_script_from_specialized(msg.content)
                    if test_file:
                        print(f"✅ Debug: Successfully extracted test file ({len(test_file)} chars)")
                        break
                    else:
                        print(f"⚠️ Debug: extract_test_script_from_specialized returned empty")
                        # Try alternative extraction
                        matches = re.findall(r'```javascript\s+(.*?)```', str(msg.content), re.DOTALL)
                        if matches:
                            test_file = matches[0].strip()
                            print(f"✅ Debug: Alternative extraction found test file ({len(test_file)} chars)")
                            break
        
        # Debug output
        print(f"🔍 Debug: page_objects count = {len(page_objects) if page_objects else 0}")
        print(f"🔍 Debug: test_file length = {len(test_file) if test_file else 0}")
        
        # Ensure we have content before calling smart operations
        if not test_file:
            print("⚠️ Warning: No test file content extracted, skipping smart file operations")
            return False
        
        # Use smart file operations
        smart_file_operations(
            page_objects, 
            test_file, 
            test_case_id, 
            output_dir, 
            intelligence_decisions
        )
        
        success = bool(page_objects and test_file)
        
        if success:
            print(f"✅ Generated {len(page_objects)} page object files")
            print(f"✅ Generated test file")
        
        return success
        
    except Exception as e:
        print(f"❌ Enhanced workflow error: {str(e)}")
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
        print("Usage: python mcp_test_generator_enhanced.py <TEST_CASE_ID> [output_dir] [target_project_path]")
        print("Example: python mcp_test_generator_enhanced.py TC-ENV-001")
        print("Example: python mcp_test_generator_enhanced.py TC-ENV-001 my_output C:/path/to/existing/e2e")
        return
        
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "complete_tests"
    target_project_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    setup_environment()
    
    if target_project_path:
        print(f"🎯 Target project: {target_project_path}")
        if not os.path.exists(target_project_path):
            print(f"⚠️ Target project path does not exist: {target_project_path}")
            print("⚠️ Continuing without intelligence analysis...")
            target_project_path = None
    else:
        print("ℹ️ No target project provided, using traditional generation")
    
    success = await generate_complete_test(test_case_id, output_dir, target_project_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())