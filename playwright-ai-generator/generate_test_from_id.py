import asyncio
import sys
import os
import re
from core.vector_retrieval import fetch_test_case_by_id
from core.browser_inspector import BrowserInspector
from core.prompt_builder import build_test_prompt, build_critique_prompt
from core.playwright_agents import PlaywrightScriptAgent, PlaywrightCriticAgent
from browser_use import Browser, BrowserConfig, Agent

# Add this new function to collect UI elements
async def collect_elements_with_browser_use(test_case):
    """Collect UI elements using browser_use based on test case."""
    # Import necessary libraries
    from langchain_openai import AzureChatOpenAI
    from dotenv import load_dotenv
    import json
    import re
    
    # Load environment variables
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(dotenv_path)
    
    # Get credentials
    app_url = os.getenv("APP_URL")
    username = os.getenv("APP_USERNAME")
    password = os.getenv("APP_PASSWORD")
    headless_str = os.getenv("APP_HEADLESS", "true").lower()
    headless = headless_str in ["true", "1", "yes"]
    
    # Create Azure OpenAI LLM
    llm = AzureChatOpenAI(
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    
    # Create browser and agent
    browser = Browser(config=BrowserConfig(headless=headless))
    
    # Create agent with specific instructions for consistent output formatting
    agent = Agent(
        task=f"""
        1. Go to "https://praveen-2.aimms.cloud/v3/users/" and log in with username '{username}' and password '{password}'
        2. For test case with steps: "{test_case['steps']}", navigate to where you need to perform these steps
        3. Identify all UI elements needed for this test case
        4. In your final report, format EACH element in EXACTLY this format:
           
           ELEMENT:
           Type: [element type]
           Text: [element text]
           Selector: [CSS selector]
           
        6. Make sure to use the EXACT format above for EVERY element you identify
        7. Use the most specific and accurate CSS selectors possible
        8. Include all buttons, inputs, and other interactive elements needed for the test case
        """,
        browser=browser,
        llm=llm
    )
    
    try:
        # Run agent
        result = await agent.run()
        
        # Save the complete agent output for debugging
        with open("agent_output.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        print("Agent output saved to agent_output.txt")
        
        # Extract elements from the agent's final result text
        elements = []
        final_text = ""
        
        # Find the 'done' action result which contains the formatted elements
        for action_result in getattr(result, "all_results", []):
            if hasattr(action_result, "is_done") and action_result.is_done:
                if hasattr(action_result, "extracted_content"):
                    final_text = action_result.extracted_content
                    break
        
        # Use regex to find element blocks in the specified format
        element_pattern = re.compile(r'ELEMENT:\s*\nType:\s*([^\n]+)\s*\nText:\s*([^\n]+)\s*\nSelector:\s*([^\n]+)', re.MULTILINE)
        matches = element_pattern.findall(final_text)
        
        if matches:
            for element_type, element_text, element_selector in matches:
                elements.append({
                    "type": element_type.strip(),
                    "text": element_text.strip(),
                    "selector": element_selector.strip()
                })
            
            print(f"Extracted {len(elements)} elements")
            
            # Save elements to JSON
            with open("collected_elements.json", "w", encoding="utf-8") as f:
                json.dump(elements, f, indent=2)
        else:
            print("No elements found in agent output using regex patterns")
            print("First 200 chars of agent output:", final_text[:200])
        
        return elements
        
    except Exception as e:
        print(f"Error collecting UI elements: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        await browser.close()
# Your existing clean_script function
def clean_script(script: str) -> str:
    """
    Clean the generated Playwright script by removing unwanted markdown,
    filename comments, and trailing tokens like 'TERMINATE'.
    """
    match = re.search(r"```javascript(.*?)```", script, re.DOTALL)
    if match:
        script = match.group(1).strip()

    script = re.sub(r"# filename:.*\n", "", script)
    script = script.replace("TERMINATE", "").strip()

    return script

# Your existing generate_playwright_test function, modified to use the new collector
async def generate_playwright_test(test_case_id: str, path: str = "/"):
    print(f"\n📥 Fetching test case '{test_case_id}'...")
    test_case = await fetch_test_case_by_id(test_case_id)
    if not test_case:
        print("❌ Test case not found.")
        return

    print(f"✅ Test case found: {test_case.get('title', 'Unknown')}")
    
    # Use the new browser_use function to collect real UI elements
    print("🔍 Collecting UI elements from application...")
    ui_elements = await collect_elements_with_browser_use(test_case)
    
    print(f"🧠 Building prompt with {len(ui_elements)} real UI elements...")
    generation_prompt = build_test_prompt(test_case, ui_elements)

    print("🛠️ Generating initial test script...")
    gen_response = PlaywrightScriptAgent.generate_reply(
        messages=[{"role": "user", "content": generation_prompt}]
    )
    generated_script = gen_response if isinstance(gen_response, str) else str(gen_response)

    print("🧪 Reviewing script with critic agent...")
    critique_prompt = build_critique_prompt(test_case, generated_script)
    critic_response = PlaywrightCriticAgent.generate_reply(
        messages=[{"role": "user", "content": critique_prompt}]
    )
    final_script = critic_response if isinstance(critic_response, str) else str(critic_response)

    final_script = clean_script(final_script)

    print("\n✅ Final Playwright Test Script:\n")
    print(final_script)

    output_dir = "tests-generated"
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{output_dir}/{test_case['id']}.spec.ts"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_script)

    print(f"\n📄 Script saved to: {filename}")

# Your existing main function
async def main():
    if len(sys.argv) < 2:
        print("⚠️ Usage: python generate_test_from_id.py <TEST_CASE_ID> [PATH]")
    else:
        test_case_id = sys.argv[1]
        path = sys.argv[2] if len(sys.argv) > 2 else "/"
        await generate_playwright_test(test_case_id, path)

if __name__ == '__main__':
    asyncio.run(main())