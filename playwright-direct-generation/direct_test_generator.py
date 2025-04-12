import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from browser_use import Browser, BrowserConfig, Agent
from langchain_openai import AzureChatOpenAI
from vector_retrieval import fetch_test_case_by_id

def extract_selectors(result, test_case_id):
    seen = set()
    selector_list = []
    selector_text = "# CSS selectors detected by browser_use\n\n"

    for history_item in result.get("history", []):
        actions = history_item.get("result", [])
        elements = history_item.get("state", {}).get("interacted_element", [])

        for action, element in zip(actions, elements):
            if not element or "css_selector" not in element:
                continue

            selector = element["css_selector"]
            if selector in seen:
                continue
            seen.add(selector)

            tag = element.get("tag_name", "unknown")
            content = action.get("extracted_content", "").lower()

            if "click" in content:
                action_type = "click"
            elif "input" in content:
                action_type = "input"
            elif "scroll" in content:
                action_type = "scroll"
            else:
                action_type = "unknown"

            selector_list.append({
                "action": action_type,
                "tag": tag,
                "text": content,
                "selector": selector
            })

            selector_text += f"Action: {action_type}\nElement: {tag}\nText: {content}\nSelector: {selector}\n\n"

    with open(f"{test_case_id}_selectors.json", "w", encoding="utf-8") as f:
        json.dump(selector_list, f, indent=2)
    with open(f"{test_case_id}_selectors.txt", "w", encoding="utf-8") as f:
        f.write(selector_text)

    print(f"✅ Extracted {len(selector_list)} selectors with actions")
    return selector_list

async def generate_playwright_test_direct(test_case_id: str):
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(dotenv_path)

    app_url = os.getenv("APP_URL")
    username = os.getenv("APP_USERNAME")
    password = os.getenv("APP_PASSWORD")
    headless = os.getenv("APP_HEADLESS", "true").lower() in ["true", "1", "yes"]

    print(f"\n📥 Fetching test case '{test_case_id}'...")
    test_case = await fetch_test_case_by_id(test_case_id)
    if not test_case:
        print("❌ Test case not found.")
        return
    print(f"✅ Test case found: {test_case.get('title', 'Unknown')}")

    llm = AzureChatOpenAI(
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    browser = Browser(config=BrowserConfig(headless=headless))

    print("🔍 Step 1: Exploring UI and collecting element information...")
    ui_agent = Agent(
        task=f"""
        You are a Playwright automation engineer using browser_use.

        Your task:
        1. Go to "https://praveen-2.aimms.cloud/v3/users/" and log in using:
           - Username: {username}
           - Password: {password}

        2. Perform this test case exactly:
        Title: {test_case['title']}
        Steps:
        {test_case['steps']}

        Expected Results:
        {test_case['expectedResults']}

        Log each interaction clearly so the system can extract selectors later.
        """,
        browser=browser,
        llm=llm
    )

    try:
        result = await ui_agent.run()

        with open(f"{test_case_id}_raw_agent_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        with open(f"{test_case_id}_raw_agent_result.json", "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print("🔍 Extracting selectors from raw agent outputs...")
        extract_selectors(json.loads(result.model_dump_json()), test_case_id)

    except Exception as e:
        print(f"❌ Error during generation: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()

async def main():
    if len(sys.argv) < 2:
        print("⚠️ Usage: python direct_test_generator.py <TEST_CASE_ID>")
    else:
        test_case_id = sys.argv[1]
        await generate_playwright_test_direct(test_case_id)

if __name__ == '__main__':
    asyncio.run(main())
