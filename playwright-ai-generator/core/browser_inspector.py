import os
from dotenv import load_dotenv
from browser_use import Browser, BrowserConfig, Agent
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..','.env'))
load_dotenv(dotenv_path)
print(f"APP_URL: {os.getenv('APP_URL')}")
print(f"APP_HEADLESS: {os.getenv('APP_HEADLESS')}")

class BrowserInspector:
    def __init__(self):
        print("DEBUG ENV:", os.getenv("APP_URL"), os.getenv("APP_HEADLESS"))
        headless_str = os.getenv("APP_HEADLESS", "true").lower()
        headless = headless_str in ["true", "1", "yes"]
        print("➡️ Headless mode:", headless)

        # Setup the browser with the browser_use BrowserConfig
        self.browser = Browser(config=BrowserConfig(
            headless=headless,  # Set headless to True/False based on environment variable
            disable_security=True
        ))

        # Setup the Agent with browser_use
        self.agent = Agent(
            task="Inspect UI elements for test generation",
            llm=ChatOpenAI(model='gpt-4o'),
            browser=self.browser,
        )

    async def get_ui_elements(self, path="/") -> list:
        try:
            base_url = os.getenv("APP_URL", "")
            full_path = base_url.rstrip("/") + path
            print(f"🌐 Navigating to path: {full_path}")

            # Use the agent to run the browser and get UI elements
            await self.agent.run()

            # Get the DOM snapshot of the page
            dom_snapshot = await self.browser.get_dom_snapshot()

            print(f"✅ Collected {len(dom_snapshot.get('elements', []))} UI elements.")
            return dom_snapshot.get("elements", [])

        except Exception as e:
            print(f"❌ UI inspection failed: {e}")
            return []

    async def close(self):
        # Close the browser after the task
        await self.browser.close()
