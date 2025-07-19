import os
from dotenv import load_dotenv
from browser_use import BrowserConfig, Browser
from browser_use.browser.context import BrowserContextConfig, BrowserContext
import autogen
from typing import TypedDict, List, Optional
from langchain_openai import AzureChatOpenAI

# Load environment variables
load_dotenv()

azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_base_url = os.getenv("AZURE_OPENAI_ENDPOINT")  # Extract the base part of the URL
azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")  # API version from your URL
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")  # Deployment name from your URL

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
TEST_CASE_ITERATIONS = 2
#LLM Configuration for AutoGen with Azure OpenAI
config_list = [
    {
        "model": azure_deployment,  # Use the deployment name instead of model name
        "api_key": azure_api_key,
        "api_version": azure_api_version,  # Include API version for Azure
        "base_url": azure_base_url,  # Use the Azure base URL
        "api_type": "azure",  # Specify that we're using Azure OpenAI
    }
]

class TestGenerationState(TypedDict):
    # Input
    feature_requirement: str
    acceptance_criteria_text: str
    similar_cases: Optional[List[dict]]
    context: str
    
    # Processing
    current_test_cases: str
    iteration_count: int
    max_iterations: int
    
    # Output
    final_test_cases: str
    critique: str
    raw_responses: List[str]  # For debugging

# ADD these LangGraph agent wrappers after existing agent definitions
def create_langgraph_llm():
    """Create LangChain LLM for LangGraph agents."""
    return AzureChatOpenAI(
        openai_api_key=azure_api_key,
        azure_deployment=azure_deployment,
        azure_endpoint=azure_base_url,
        api_version=azure_api_version,
        temperature=0.2
    )

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

TestCaseOptimizer = autogen.AssistantAgent(
    name="TestCase_Optimizer",
    llm_config={"config_list": config_list},
)