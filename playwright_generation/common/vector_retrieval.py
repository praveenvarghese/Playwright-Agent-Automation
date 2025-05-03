# vector_retrieval.py
import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Load environment variables
def get_search_client():
    """Returns an authenticated Azure Cognitive Search client."""
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(dotenv_path)
    
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
    
    if not (endpoint and api_key and index_name):
        raise ValueError("Azure Search config missing. Check .env file.")
    
    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(api_key)
    )

async def fetch_test_case_by_id(test_case_id):
    """
    Fetch a single test case by its ID from the Azure Vector Search index.
    
    Args:
        test_case_id (str): e.g., "TC-ENV-008"
    
    Returns:
        dict or None: The test case data if found, else None.
    """
    client = get_search_client()
    print(f"🔍 Searching for test case ID: {test_case_id}")

    try:
        results = client.search(
            search_text="",  # empty = use filter only
            filter=f"id eq '{test_case_id}'",
            select=["*"]
        )
        for result in results:
            return dict(result)

        print("⚠️ Test case not found.")
        return None

    except Exception as e:
        print(f"❌ Azure Search error: {str(e)}")
        return None