#!/usr/bin/env python3
"""
Debug script to troubleshoot the browser_use module.
"""

import os
import sys
import traceback
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

print("🔍 Debugging browser_use imports...")
print("\n📋 Environment variables:")
print(f"  PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
print(f"  Current directory: {os.getcwd()}")

# Try to import from browser_use package
try:
    print("\n🔄 Attempting to import browser_use...")
    from browser_use import BrowserConfig, Browser
    print("✅ Successfully imported BrowserConfig and Browser")
except ImportError as e:
    print(f"❌ Error importing BrowserConfig, Browser: {str(e)}")
    traceback.print_exc()

try:
    print("\n🔄 Attempting to import browser_use context...")
    from browser_use.browser.context import BrowserContextConfig, BrowserContext
    print("✅ Successfully imported BrowserContextConfig and BrowserContext")
except ImportError as e:
    print(f"❌ Error importing BrowserContextConfig, BrowserContext: {str(e)}")
    traceback.print_exc()

# If we got this far, try to create a browser instance
if 'BrowserConfig' in locals() and 'Browser' in locals():
    try:
        print("\n🔄 Attempting to create browser instance...")
        browser_config = BrowserConfig(
            headless=True,
            disable_security=True
        )
        browser = Browser(config=browser_config)
        print("✅ Successfully created browser instance")
        
        # Try to create context if BrowserContext is available
        if 'BrowserContextConfig' in locals() and 'BrowserContext' in locals():
            try:
                print("\n🔄 Attempting to create browser context...")
                context_config = BrowserContextConfig(
                    wait_for_network_idle_page_load_time=3.0,
                    browser_window_size={'width': 1280, 'height': 1100},
                    locale='en-US',
                    highlight_elements=True,
                    viewport_expansion=500,
                )
                context = BrowserContext(browser=browser, config=context_config)
                print("✅ Successfully created browser context")
            except Exception as e:
                print(f"❌ Error creating browser context: {str(e)}")
                traceback.print_exc()
    except Exception as e:
        print(f"❌ Error creating browser instance: {str(e)}")
        traceback.print_exc()

print("\n✅ Debug script completed")