import asyncio
from browser_use import BrowserConfig, Browser
from browser_use.browser.context import BrowserContextConfig, BrowserContext

async def main():
    # Setup browser
    print("Setting up browser...")
    browser_config = BrowserConfig(headless=False, disable_security=True)
    browser = Browser(config=browser_config)
    
    context_config = BrowserContextConfig()
    context = BrowserContext(browser=browser, config=context_config)
    
    # Create page - using the correct method
    print("Creating page...")
    page = await browser.new_page(context=context)
    
    print("Navigating to your application...")
    await page.goto("https://vlad2.aimms-dev.cloud/v3/users/")
    
    # Try to find some elements
    print("Looking for elements...")
    # Use the proper API for finding elements
    buttons = await page.query_selector_all('button')
    print(f"Found {len(buttons)} buttons")
    
    # Print some info about the buttons
    for i, button in enumerate(buttons):
        text = await button.text_content()
        print(f"Button {i+1}: {text}")
    
    # Close browser
    print("Done. Closing browser.")
    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())