import autogen
import os
from dotenv import load_dotenv

# Load Azure OpenAI credentials from .env
load_dotenv()

azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

config_list = [
    {
        "model": azure_deployment,
        "api_key": azure_api_key,
        "api_version": azure_api_version,
        "base_url": azure_base_url,
        "api_type": "azure",
    }
]

# Define AutoGen Agents for Playwright
PlaywrightScriptAgent = autogen.AssistantAgent(
    name="PlaywrightScriptAgent",
    llm_config={"config_list": config_list},
)

PlaywrightCriticAgent = autogen.AssistantAgent(
    name="PlaywrightCriticAgent",
    llm_config={"config_list": config_list},
)
