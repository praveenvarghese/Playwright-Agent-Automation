import os
import asyncio
from dotenv import load_dotenv
from browser_use import Browser, BrowserConfig, Agent
from langchain_openai import ChatOpenAI

# Load environment variables from parent directory (two levels up)
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.env'))
load_dotenv(dotenv_path)
print(f"Loading .env from: {dotenv_path}")

class UIElementCollector:
    def __init__(self):
        """Initialize the UI Element Collector with browser_use."""
        # Get app config from environment variables
        self.app_url = os.getenv("APP_URL", "")
        self.username = os.getenv("APP_USERNAME", "")
        self.password = os.getenv("APP_PASSWORD", "")
        
        # Get headless setting from env
        headless_str = os.getenv("APP_HEADLESS", "true").lower()
        self.headless = headless_str in ["true", "1", "yes"]
        
        print(f"Initializing UI Element Collector")
        print(f"  URL: {self.app_url}")
        print(f"  Headless: {self.headless}")
        
        # Setup the browser with browser_use
        self.browser = Browser(config=BrowserConfig(
            headless=self.headless,
            disable_security=True
        ))
        
        # Initialize an agent but don't set task yet (will be set per operation)
        self.agent = Agent(
            task=f"Navigate to {self.app_url} and prepare for authentication",
            llm=ChatOpenAI(model='gpt-4o'),
            browser=self.browser,
        )
        
    async def authenticate(self):
        """
        Handle authentication to the application.
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        try:
            print("Starting authentication process...")
            
            # Create a very specific task for authentication
            auth_task = f"""
            You must follow these exact steps in order:
            1. Navigate to the URL {self.app_url}
            2. The page will redirect to a login form
            3. Find the username/email input field
            4. Enter this username: {self.username}
            5. Find the password input field
            6. Enter this password: {self.password}
            7. Find and click the login/submit button
            8. Wait for the page to fully load after login
            9. Verify you are logged in by checking for user-specific elements
            
            Do NOT visit any other websites. Stay focused on this authentication task.
            """
            
            # Update the agent's task for authentication
            self.agent.task = auth_task
            
            # Run the agent to perform authentication
            await self.agent.run()
            
            # Check if we're still on the login page
            page_content = True
            current_content = str(page_content)
            
            if "login" in current_content.lower() or "password" in current_content.lower():
                print("WARNING: Still on login page. Authentication may have failed.")
                return False
            else:
                print("Successfully authenticated!")
                return True
                
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return False
        
    async def collect_elements(self, path="/"):
        """
        Navigate to the specified path and collect UI elements.
        
        Args:
            path (str): The path to navigate to (appended to base URL)
            
        Returns:
            list: Collection of UI elements with their properties
        """
        try:
            # First authenticate
            auth_success = await self.authenticate()
            if not auth_success:
                print("Authentication failed. Cannot collect UI elements.")
                return []
            
            # Now navigate to the specific path
            target_url = f"{self.app_url}{path}"
            print(f"Navigating to: {target_url}")
            
            # Create specific navigation and collection instructions
            collection_task = f"""
            You have successfully authenticated to the application.
            
            Now, follow these exact steps:
            1. Navigate to the specific URL: {target_url}
            2. Wait for the page to fully load
            3. Do NOT navigate away from this URL
            4. Analyze the page and identify ALL UI elements including:
               - Buttons, inputs, dropdowns, links, forms
               - Text fields, labels, headings
               - Tables, lists, and other structured content
               - Any interactive elements
            5. Collect detailed information about each element
            
            Stay on this exact URL and do not navigate elsewhere.
            """
            
            # Update the agent's task
            self.agent.task = collection_task
            
            # Run the agent to navigate and collect elements
            print("Collecting UI elements...")
            await self.agent.run()
            
            # Get the DOM snapshot with all UI elements
            print("Getting DOM snapshot...")
            dom_snapshot = await self.browser.get_dom_snapshot()
            elements = dom_snapshot.get("elements", [])
            
            # Process elements into a more usable structure
            processed_elements = []
            for elem in elements:
                # Skip elements without a selector or that are invisible
                if not elem.get("selector"):
                    continue
                    
                processed_elements.append({
                    "type": elem.get("tagName", "unknown").lower(),
                    "text": elem.get("textContent", "").strip(),
                    "name": elem.get("name", ""),
                    "id": elem.get("id", ""),
                    "placeholder": elem.get("placeholder", ""),
                    "selector": elem.get("selector", ""),
                    "aria_label": elem.get("ariaLabel", ""),
                    "value": elem.get("value", "")
                })
            
            print(f"Collected {len(processed_elements)} UI elements")
            return processed_elements
            
        except Exception as e:
            print(f"Error collecting UI elements: {str(e)}")
            return []
    
    async def close(self):
        """Close the browser when done."""
        await self.browser.close()
        print("Browser closed")