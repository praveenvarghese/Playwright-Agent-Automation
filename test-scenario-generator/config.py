# config.py

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv(dotenv_path=Path("../.env"))

# Azure OpenAI configuration loaded from environment variables
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Add embedding model deployment name
azure_embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

# Define the common config list that can be reused
config_list = [
    {
        "model": azure_deployment,            # The model you're using (e.g., GPT-4)
        "api_key": azure_api_key,            # The API key
        "api_version": azure_api_version,    # The API version (e.g., v1)
        "base_url": azure_base_url,          # The base URL of Azure OpenAI
        "api_type": "azure",                 # We're using the Azure OpenAI service
    }
]