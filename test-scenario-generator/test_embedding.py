# test_embedding.py
"""
A simple script to test Azure OpenAI embedding model.
"""

import os
import requests
import json

# Get environment variables
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

# Print current settings
print("Current settings:")
print(f"AZURE_OPENAI_ENDPOINT: {AZURE_OPENAI_ENDPOINT}")
print(f"AZURE_OPENAI_API_VERSION: {AZURE_OPENAI_API_VERSION}")
print(f"AZURE_OPENAI_EMBEDDING_DEPLOYMENT: {AZURE_OPENAI_EMBEDDING_DEPLOYMENT}")
print(f"API Key: {'*' * 5}{AZURE_OPENAI_API_KEY[-4:] if AZURE_OPENAI_API_KEY else 'Not set'}")

# List available deployments
print("\nListing available deployments...")
url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments?api-version={AZURE_OPENAI_API_VERSION}"
headers = {
    "api-key": AZURE_OPENAI_API_KEY
}

try:
    response = requests.get(url, headers=headers)
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("Available deployments:")
        for deployment in data.get("data", []):
            print(f"- ID: {deployment.get('id')} | Model: {deployment.get('model')}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {str(e)}")

# Test embedding generation
print("\nTesting embedding generation...")
# Based on the documentation, the most recent URL format is:
url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}/embeddings?api-version={AZURE_OPENAI_API_VERSION}"
print(f"URL: {url}")

headers = {
    "Content-Type": "application/json",
    "api-key": AZURE_OPENAI_API_KEY
}

data = {
    "input": "This is a test of the embedding model."
}

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        embedding = result.get("data", [{}])[0].get("embedding", [])
        print(f"Success! Embedding length: {len(embedding)}")
        # Print first 5 values of embedding
        print(f"First few values: {embedding[:5]}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {str(e)}")

# Try alternative URL format
print("\nTrying alternative URL format (might be needed for certain API versions)...")
# Remove trailing slash if present
if AZURE_OPENAI_ENDPOINT.endswith("/"):
    alternative_endpoint = AZURE_OPENAI_ENDPOINT[:-1]
else:
    alternative_endpoint = AZURE_OPENAI_ENDPOINT

url = f"{alternative_endpoint}/openai/deployments/{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}/embeddings?api-version={AZURE_OPENAI_API_VERSION}"
print(f"URL: {url}")

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        embedding = result.get("data", [{}])[0].get("embedding", [])
        print(f"Success! Embedding length: {len(embedding)}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {str(e)}")

print("\nSuggested fixes if still encountering errors:")
print("1. Check if the API version is compatible - try '2024-02-01' (stable) or '2024-03-01-preview'")
print("2. Ensure the endpoint URL is correct and has no trailing slash")
print("3. Confirm the embedding model deployment name matches exactly what's in Azure Portal")
print("4. Verify your API key has access to the embedding model")