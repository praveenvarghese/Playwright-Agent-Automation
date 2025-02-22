import os
from dotenv import load_dotenv
from browser_use import BrowserConfig, Browser
from browser_use.browser.context import BrowserContextConfig, BrowserContext
import autogen

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Configure browser settings
browser_config = BrowserConfig(
    headless=True,  # Run in headless mode
    disable_security=True
)

# Define browser context configuration
context_config = BrowserContextConfig(
    wait_for_network_idle_page_load_time=3.0,
    browser_window_size={'width': 1280, 'height': 1100},
    locale='en-US',
    highlight_elements=True,
    viewport_expansion=500,
)

# Initialize browser and context
browser = Browser(config=browser_config)
context = BrowserContext(browser=browser, config=context_config)

# 🎯 LLM Configuration for AutoGen
config_list = [
    {
        "model": "gpt-4o-mini",
        "api_key": api_key,
    }
]

# **Define Agents**
TestCaseAgent = autogen.AssistantAgent(
    name="TestCase_Generator",
    llm_config={"config_list": config_list},
)

TestCaseCritic = autogen.AssistantAgent(
    name="TestCase_Critic",
    llm_config={"config_list": config_list},
)

UIAgent = autogen.AssistantAgent(
    name="UI_Generator",
    llm_config={"config_list": config_list},
)

UICritic = autogen.AssistantAgent(
    name="UI_Critic",
    llm_config={"config_list": config_list},
)
