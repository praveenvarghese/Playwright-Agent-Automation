import os
import asyncio
from dotenv import load_dotenv
from browser_use import Browser, BrowserConfig, Agent
from langchain_openai import ChatOpenAI

# Load environment variables from the correct location (parent directory)
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.env'))
load_dotenv(dotenv_path)
print(f"Loading .env from: {dotenv_path}")

async def test_authentication():
    """Test authenticating with the application."""
    print("\n=== TESTING AUTHENTICATION ===")
    
    # Get configuration from environment
    app_url = os.getenv("APP_URL", "")
    username = os.getenv("APP_USERNAME", "")
    password = os.getenv("APP_PASSWORD", "")
    headless_str = os.getenv("APP_HEADLESS", "true").lower()
    headless = headless_str in ["true", "1", "yes"]
    
    print(f"Target URL: {app_url}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password) if password else 'Not Set'}")
    print(f"Headless mode: {headless}")
    
    # Setup the browser with visible mode for debugging
    browser = Browser(config=BrowserConfig(
        headless=headless,
        disable_security=True
    ))
    
    # Create a very specific task for authentication
    auth_task = f"""
    You must follow these exact steps in order:
    1. Navigate to the URL {app_url}
    2. The page will redirect to a login form
    3. Find the username/email input field
    4. Enter this username: {username}
    5. Find the password input field
    6. Enter this password: {password}
    7. Find and click the login/submit button
    8. Wait for the page to fully load after login
    9. Verify you are logged in by checking for user-specific elements
    
    Do NOT visit any other websites. Stay focused on this authentication task.
    """
    
    # Create the agent with our specific authentication task
    agent = Agent(
        task=auth_task,
        llm=ChatOpenAI(model='gpt-4o'),
        browser=browser,
    )
    
    try:
        # Run the agent
        print("\nStarting authentication process...")
        await agent.run()
        
        # Get current page content to verify login status
        print("\nChecking current page after authentication...")
        current_content = await browser.get_page_content()
        
        # Check if we're still on the login page or successfully logged in
        if "login" in current_content.lower() or "password" in current_content.lower():
            print("⚠️ WARNING: Still on login page. Authentication may have failed.")
        else:
            print("✅ Successfully authenticated! No longer on login page.")
        
        # Get current URL
        page_content = await browser.extract_content(goal="Get current URL and page title")
        print(f"\nCurrent page: {page_content.get('url', 'Unknown')}")
        print(f"Page title: {page_content.get('title', 'Unknown')}")
        
        # Get DOM elements to verify we have access to the page
        print("\nGetting DOM elements...")
        dom = await browser.get_dom_snapshot()
        elements = dom.get("elements", [])
        print(f"Found {len(elements)} elements on the page")
        
        # Show a few example elements
        print("\nExample elements:")
        for i, elem in enumerate(elements[:5]):
            elem_type = elem.get('tagName', 'unknown')
            elem_text = elem.get('textContent', '')[:30]
            if elem_text:
                elem_text = elem_text.strip()
            print(f"{i+1}. Type: {elem_type}, Text: {elem_text}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
    finally:
        # Always close the browser
        await browser.close()
        print("\nBrowser closed")

if __name__ == "__main__":
    asyncio.run(test_authentication())