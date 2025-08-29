# document_retrieval.py
import os
import json
import requests
import re
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# Azure Cognitive Search Configuration
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
# Use a hardcoded index name instead of relying solely on environment variables
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_DOCUMENT_INDEX_NAME", "requirements-index")
# Set a specific API version for Azure Search
AZURE_SEARCH_API_VERSION = "2023-11-01"  # Use a more recent API version

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
# Use the specific embedding deployment name 
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

# Print configuration for debugging
print("Azure Search Configuration:")
print(f"AZURE_SEARCH_ENDPOINT: {AZURE_SEARCH_ENDPOINT}")
print(f"AZURE_SEARCH_INDEX_NAME: {AZURE_SEARCH_INDEX_NAME}")
print(f"AZURE_SEARCH_API_VERSION: {AZURE_SEARCH_API_VERSION}")
print(f"AZURE_SEARCH_KEY: {'*' * 5}{AZURE_SEARCH_KEY[-4:] if AZURE_SEARCH_KEY else 'Not set'}")

def sanitize_key(key):
    """
    Sanitize a key for Azure Search to ensure it only contains valid characters.
    Azure Search keys can only contain letters, digits, underscore (_), dash (-), or equal sign (=).
    """
    # Replace any invalid characters with underscores
    # First, replace periods with underscores
    sanitized = key.replace('.', '_')
    
    # Then use regex to replace any other invalid characters
    sanitized = re.sub(r'[^a-zA-Z0-9_\-=]', '_', sanitized)
    
    return sanitized

def generate_embeddings(text):
    """
    Generate embeddings for text using Azure OpenAI embedding model.
    """
    # Handle empty text
    if not text or text.strip() == "":
        raise ValueError("Cannot generate embeddings for empty text")
    
    # Fix for double slash - ensure endpoint doesn't end with a slash
    endpoint = AZURE_OPENAI_ENDPOINT
    if endpoint.endswith("/"):
        endpoint = endpoint[:-1]
    
    # Make sure to use the embedding-specific deployment
    url = f"{endpoint}/openai/deployments/{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}/embeddings?api-version={AZURE_OPENAI_API_VERSION}"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }
    
    body = {
        "input": text,
    }
    
    # For debugging
    print(f"Calling embedding API at: {url}")
    
    # Make the request
    response = requests.post(url, headers=headers, json=body)
    
    if response.status_code == 200:
        return response.json()["data"][0]["embedding"]
    else:
        error_message = f"Error generating embeddings: {response.text}"
        print(error_message)
        raise Exception(error_message)

def retrieve_application_context(requirement_text, top_k=3):
    """
    Retrieve relevant application context based on the requirement text.
    
    Args:
        requirement_text (str): The requirement text to find context for
        top_k (int): Number of relevant documents to retrieve
        
    Returns:
        str: Concatenated relevant application context
    """
    # Generate embeddings for the query
    query_embedding = generate_embeddings(requirement_text)
    
    # Initialize the search client with explicit API version
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY),
        api_version=AZURE_SEARCH_API_VERSION
    )
    
    # Create a vector query using VectorizedQuery
    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k,
        fields="embedding"
    )
    
    # Use the field names from your schema
    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["id", "requirement_text"],  # Matches your schema
        top=top_k
    )
    
    # Extract and concatenate the context from the results
    contexts = []
    for result in results:
        # Store the original filename in the output
        original_filename = result["id"].replace('_rst', '.rst')
        contexts.append(f"Document: {original_filename}\n{result['requirement_text']}")
    
    # Join the contexts with double newlines for better readability
    return "\n\n".join(contexts) if contexts else ""

def process_rst_file(file_path):
    """
    Process an RST file to extract its content.
    This simple version just reads the content directly.
    For more complex RST parsing, consider using docutils.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content

def upload_application_document(document_path):
    """
    Upload an application document to the vector database.
    
    Args:
        document_path (str): Path to the document file
    """
    # Process different file types appropriately
    _, file_extension = os.path.splitext(document_path)
    
    # Load and process the document based on file type
    if file_extension.lower() == '.rst':
        document_text = process_rst_file(document_path)
    else:
        # Default text file handling
        with open(document_path, "r", encoding="utf-8") as f:
            document_text = f.read()
    
    # Truncate if the document is too large
    # Most embedding models have a token limit - adjust this as needed
    max_chars = 8000  # Approximate character limit for embedding models
    if len(document_text) > max_chars:
        print(f"Warning: Document {document_path} truncated from {len(document_text)} to {max_chars} characters")
        document_text = document_text[:max_chars]
    
    # Generate embedding for the document
    embedding = generate_embeddings(document_text)
    
    # Generate a document ID (using filename as ID) and sanitize it
    original_id = os.path.basename(document_path)
    doc_id = sanitize_key(original_id)
    
    # Create the document object matching your schema
    document = {
        "id": doc_id,
        "requirement_text": document_text,
        "embedding": embedding
    }
    
    # Initialize the search client with explicit API version
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY),
        api_version=AZURE_SEARCH_API_VERSION
    )
    
    # For debugging
    print(f"Uploading document to index: {AZURE_SEARCH_INDEX_NAME}")
    print(f"Original filename: {original_id}")
    print(f"Sanitized document ID: {doc_id}")
    print(f"Document fields: {list(document.keys())}")
    
    # Upload the document
    try:
        search_client.upload_documents([document])
        return f"Document {original_id} uploaded successfully!"
    except Exception as e:
        detailed_error = f"Error uploading {original_id}: {str(e)}"
        print(detailed_error)
        raise Exception(detailed_error)

def upload_documents_from_directory(directory_path):
    """
    Upload all documents from a directory to the vector database.
    
    Args:
        directory_path (str): Path to the directory containing documents
    """
    uploaded = []
    
    # Define supported file extensions, now including .rst
    supported_extensions = ('.txt', '.md', '.py', '.html', '.rst', '.js', '.css', '.json')
    
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        
        # Skip directories and non-supported files
        if os.path.isdir(file_path) or not filename.lower().endswith(supported_extensions):
            continue
        
        try:
            # Upload the document
            result = upload_application_document(file_path)
            uploaded.append(result)
        except Exception as e:
            uploaded.append(f"Error uploading {filename}: {str(e)}")
    
    return uploaded