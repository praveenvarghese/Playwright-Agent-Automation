#!/usr/bin/env python3
"""
MCP Test Generator - Based on your working POC
Clean separation: MCP automation + Page Object generation
"""

import asyncio
import json
import os
import sys
import warnings
from openai import AzureOpenAI
from dotenv import load_dotenv
import logging

# Suppress warnings early
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed transport.*")

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv()

async def generate_test_with_mcp(test_case_id: str, output_dir: str = "mcp_tests"):
    """Generate complete test using MCP automation + existing POM generation"""
    
    print(f"🚀 Generating test for {test_case_id}")
    
    # Step 1: Get test case
    test_case = await fetch_test_case(test_case_id)
    if not test_case:
        return False
        
    # Step 2: Run MCP automation  
    execution_log = await run_mcp_automation(test_case_id, test_case)
    if not execution_log:
        return False
        
    # Step 3: Extract selectors
    selectors = extract_selectors(execution_log)
    with open(f"{test_case_id}_selectors.json", "w") as f:
        json.dump(selectors, f, indent=2)
    print(f"✅ Generated {len(selectors)} selectors")
        
    # Step 4: Generate Page Objects
    os.makedirs(output_dir, exist_ok=True)
    success = await generate_page_objects(test_case_id, test_case, selectors, output_dir)
    
    if success:
        print(f"🎉 Test generation completed successfully for {test_case_id}")
        print(f"📁 Files saved in {output_dir}")
    return success

async def fetch_test_case(test_case_id):
    """Fetch test case from vector database"""
    try:
        from playwright_generation.common.vector_retrieval import fetch_test_case_by_id
        print(f"📚 Fetching test case {test_case_id}")
        test_case = await fetch_test_case_by_id(test_case_id)
        if test_case:
            print(f"✅ Found: {test_case.get('title', 'Unknown')}")
        return test_case
    except Exception as e:
        print(f"❌ Error fetching test case: {e}")
        return None

async def run_mcp_automation(test_case_id, test_case):
    """Run MCP automation using your proven POC approach"""
    
    from playwright_generation.mcp_helpers.mcp_manager import WorkingMCPManager
    
    manager = WorkingMCPManager()
    execution_log = []
    
    try:
        print("🎭 Starting MCP automation")
        await manager.start_server()
        
        # Execute test using POC conversation approach
        execution_log = await execute_with_conversation(manager, test_case_id, test_case)
        
        # Save detailed log
        with open(f"{test_case_id}_mcp_execution_log.json", "w") as f:
            json.dump(execution_log, f, indent=2)
        print(f"📄 Detailed execution log saved to {test_case_id}_mcp_execution_log.json")
        
        return execution_log
        
    except Exception as e:
        print(f"❌ MCP automation failed: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await manager.cleanup()

async def execute_with_conversation(manager, test_case_id, test_case):
    """Execute test using AI conversation (your POC approach)"""
    
    # Initialize OpenAI
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview"
    )
    
    # Create test prompt from database data + context
    test_prompt = f"""
Execute this test case step by step:

CONTEXT:
- Application URL: {os.getenv('APP_URL')}
- Username: {os.getenv('APP_USERNAME')}
- Password: {os.getenv('APP_PASSWORD')}

🚨  CRITICAL: Use Playwright locator methods for all interactions:
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

Provide detailed technical information about:
- CSS selectors used (must be CSS format)
- Actions performed 
- Values entered
- Results observed

Continue until all test steps are completed or you encounter an error.
"""

    # Initialize conversation exactly like your POC
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

    # Execute exactly like your POC
    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

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
                    
                    # Execute tool
                    result = await manager.execute_tool(tool_name, args)
                    
                    # Log execution
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
    """Simple, universal selector extraction using LLM"""
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
            # Extract raw playwright code
            playwright_code = extract_playwright_code(result)
            
            if playwright_code:
                # Let LLM parse it into clean format
                parsed_action = llm_parse_action(tool, playwright_code, args)
                if parsed_action:
                    selectors.append(parsed_action)
                else:
                    # Fallback if LLM parsing fails
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
                
                # Look for lines that start with "await page."
                lines = text.split('\n')
                for line in lines:
                    clean_line = line.strip()
                    if clean_line.startswith('await page.'):
                        # Extract just the locator part, not the full line
                        import re
                        pattern = r"await page\.(getBy\w+\([^)]+\))\.(\w+)\("
                        match = re.search(pattern, clean_line)
                        
                        if match:
                            locator_part = match.group(1)
                            return locator_part  # Return just "getByRole('textbox', { name: 'Username' })"
                        
                        return clean_line  # Fallback to full line
                        
    except Exception as e:
        logging.warning(f"Error extracting Playwright code: {e}")
        
    return None

def llm_parse_action(tool, playwright_code, args):
    """Use LLM to parse any Playwright selector into clean format"""
    
    # Initialize Azure OpenAI client
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    )
    
    # IMPROVED prompt based on other LLM's feedback
    prompt = f"""
You are an expert at extracting UI actions and selectors from Playwright automation logs.

Given:
- Tool: {tool}
- Playwright code: {playwright_code}
- Args: {json.dumps(args)}

**Requirements:**
1. ALWAYS extract and include a "target" object that describes the selector:
    - If getByRole: "target": {{ "type": "role", "role": "<role>", "name": "<name>" }}
    - If getByText: "target": {{ "type": "text", "text": "<text>" }}
    - If getByLabel: "target": {{ "type": "label", "label": "<label>" }}
    - If generic CSS: "target": {{ "type": "css", "selector": "<css-selector>" }}
    - If other/fallback: "target": {{ "type": "<other-type>", ... }}
2. ALWAYS include a "rawSelector" field with the exact Playwright locator string.
3. For input actions: include "value".
4. For click actions: DO NOT include a "value" field.
5. ALWAYS include an "elementName" field for human readability.
6. Output ONLY the JSON object, with ALL required fields.

**EXAMPLES:**

- Input with getByRole:
{{
  "action": "input",
  "target": {{ "type": "role", "role": "textbox", "name": "Username" }},
  "value": "admin",
  "rawSelector": "getByRole('textbox', {{ name: 'Username' }})",
  "elementName": "Username input"
}}

- Click with getByText:
{{
  "action": "click",
  "target": {{ "type": "text", "text": "Login" }},
  "rawSelector": "getByText('Login')",
  "elementName": "Login button"
}}

- Input with getByLabel:
{{
  "action": "input",
  "target": {{ "type": "label", "label": "Password" }},
  "value": "secret",
  "rawSelector": "getByLabel('Password')",
  "elementName": "Password input"
}}

- Fallback for unknown selector:
{{
  "action": "click",
  "target": {{ "type": "css", "selector": "#main > button.primary" }},
  "rawSelector": "#main > button.primary",
  "elementName": "Primary button"
}}

**INSTRUCTIONS:**
- Parse the Playwright code and extract a JSON object matching the above requirements and style. Do not return explanations—only the JSON object.
"""
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse the JSON response
        parsed_result = json.loads(result_text)
        
        # Add the value for input actions if not present
        if tool == "browser_type" and "value" not in parsed_result:
            parsed_result["value"] = args.get("text", "")
        
        return parsed_result
        
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse LLM JSON response: {result_text}. Error: {e}")
        return None
    except Exception as e:
        logging.error(f"LLM parsing failed: {e}")
        return None
      
async def generate_page_objects(test_case_id, test_case, selectors, output_dir):
    """Generate Page Objects using existing orchestrator"""
    try:
        from playwright_generation.orchestration.agent_orchestrator import PlaywrightAgentOrchestrator
        
        print("🏗️ Generating Page Object Models")
        orchestrator = PlaywrightAgentOrchestrator(output_dir=output_dir)
        
        # Use existing workflow
        success = await orchestrator.generate_from_selectors(test_case_id, test_case, selectors)
        return success
        
    except Exception as e:
        print(f"❌ Page object generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def setup_environment():
    """Setup and validate environment"""
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
        print("Usage: python mcp_test_generator.py <TEST_CASE_ID> [output_dir]")
        return
        
    test_case_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "mcp_tests"
    
    setup_environment()
    
    success = await generate_test_with_mcp(test_case_id, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())