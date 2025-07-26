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

PREREQUISITE STEPS:
1. Navigate to the application URL
2. Wait for page to load
3. Look for login form elements (username, password fields)
4. Fill in username with the provided credentials
5. Fill in password and submit

TEST STEPS:
{test_case.get('steps', '')}

EXPECTED RESULTS:
{test_case.get('expectedResults', '')}

Provide detailed technical information about:
- CSS selectors used
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
    """Extract REAL Playwright locators from MCP execution log"""
    selectors = []
    
    for i, entry in enumerate(execution_log):
        tool = entry["tool"]
        args = entry["args"]
        result = entry.get("result", {})
        
        # Extract the working Playwright locator from MCP response
        playwright_locator = extract_playwright_locator(result)
        element_name = args.get("element", "")
        
        if tool == "browser_navigate":
            selectors.append({
                "action": "navigate",
                "tag": "page", 
                "text": f"Navigate to {args.get('url', '')}",
                "selector": "",
                "url": args.get('url', '')
            })
            
        elif tool == "browser_type":
            input_text = args.get("text", "")
            selectors.append({
                "action": "input",
                "tag": "input",
                "text": f"⌨️ Input {input_text} into {element_name}",
                "selector": playwright_locator,  # REAL locator from MCP
                "input_value": input_text,
                "element_name": element_name
            })
            
        elif tool == "browser_click":
            selectors.append({
                "action": "click", 
                "tag": "button",
                "text": f"🖱️ Click {element_name}",
                "selector": playwright_locator,  # REAL locator from MCP
                "element_name": element_name
            })
    
    return selectors

def extract_playwright_locator(result):
    """
    Extract Playwright locator from MCP tool response.
    
    Input: MCP result containing text like:
    "await page.getByRole('textbox', { name: 'Username' }).fill('admin');"
    
    Output: "getByRole('textbox', { name: 'Username' })"
    """
    try:
        # Get the text content from MCP response
        if not isinstance(result, dict) or "content" not in result:
            return None
            
        for content_item in result["content"]:
            if isinstance(content_item, dict) and "text" in content_item:
                text = content_item["text"]
                
                # Look for Playwright code lines
                lines = text.split('\n')
                for line in lines:
                    clean_line = line.strip()
                    if clean_line.startswith('await page.'):
                        # Extract locator part from line like:
                        # "await page.getByRole('textbox', { name: 'Username' }).fill('admin');"
                        
                        import re
                        # Pattern: await page.LOCATOR.ACTION(...)
                        pattern = r"await page\.(.+?)\.(fill|click|press|selectOption|check|clear|goto)"
                        match = re.search(pattern, clean_line)
                        
                        if match:
                            locator_part = match.group(1)
                            print(f"✅ Extracted locator: {locator_part}")
                            return locator_part
                            
    except Exception as e:
        print(f"⚠️ Error extracting Playwright locator: {e}")
        
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