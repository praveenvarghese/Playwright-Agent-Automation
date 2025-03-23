import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
from azure.search.documents import SearchClient
from azure.search.documents._generated.models import VectorQuery as GeneratedVectorQuery
from azure.search.documents.models import VectorQuery
from azure.core.credentials import AzureKeyCredential

class EmbeddingsGenerator:
    def __init__(self):
        """
        Initialize the embeddings generator with Azure OpenAI and 
        Azure Cognitive Search configurations.
        """
        # Load environment variables
        load_dotenv()
        
        # Azure OpenAI Configuration
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        self.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.azure_embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
        
        # Azure Cognitive Search Configuration
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "testcases-vector-index")
        
        # Validate configurations
        self._validate_config()
        
        # Initialize Search client
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.search_key)
        )
    
    def _validate_config(self):
        """Validate that all required configuration values are present."""
        missing_vars = []
        
        # Check Azure OpenAI config
        if not self.azure_api_key:
            missing_vars.append("AZURE_OPENAI_API_KEY")
        if not self.azure_base_url:
            missing_vars.append("AZURE_OPENAI_ENDPOINT")
        if not self.azure_deployment:
            missing_vars.append("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if not self.azure_api_version:
            missing_vars.append("AZURE_OPENAI_API_VERSION")
            
        # Check Azure Search config
        if not self.search_endpoint:
            missing_vars.append("AZURE_SEARCH_ENDPOINT")
        if not self.search_key:
            missing_vars.append("AZURE_SEARCH_KEY")
            
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    def generate_embedding(self, text):
        """
        Generate embeddings for a text using Azure OpenAI.
        
        Args:
            text (str): The text to generate embedding for
            
        Returns:
            list: The embedding vector
        """
        url = f"{self.azure_base_url}/openai/deployments/{self.azure_deployment}/embeddings?api-version={self.azure_api_version}"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": self.azure_api_key
        }
        
        data = {
            "input": text,
            "model": self.azure_deployment
        }
        
        retry_count = 0
        max_retries = 3
        
        start_time = time.time()
        while retry_count < max_retries:
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                embedding_data = response.json()
                embedding = embedding_data["data"][0]["embedding"]
                
                return embedding
            except Exception as e:
                print(f"Error generating embedding: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)  # Wait before retrying
                else:
                    print("Max retries reached. Failed to generate embedding.")
                    return None
    
    
        """
        Parse a test case from generated text output.
        Simplified to extract only ID, Title, Steps, and Expected Results.
        
        Args:
            text (str): The generated test case text
            
        Returns:
            dict: Structured test case
        """
        # Simple parsing based on simplified format
        lines = text.strip().split('\n')
        test_case = {
            "id": "",
            "title": "",
            "steps": "",
            "expectedResults": ""
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if "Test Case ID:" in line or "ID:" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    # Clean ID value - remove any invalid characters
                    raw_id = parts[1].strip()
                    # Remove asterisks and other invalid characters
                    clean_id = ''.join(c for c in raw_id if c.isalnum() or c in ['-', '_', '='])
                    test_case["id"] = clean_id
            elif "Test Case Title:" in line or "Title:" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    raw_title = parts[1].strip()
                    clean_title = raw_title.replace('*', '').strip()
                    test_case["title"] = clean_title
            elif "Test Steps:" in line or "Steps:" in line:
                current_section = "steps"
                test_case["steps"] = ""
            elif "Expected Results:" in line:
                current_section = "expectedResults"
                test_case["expectedResults"] = ""
            elif current_section == "steps" and line and "Expected Results:" not in line:
                test_case["steps"] += line + "\n"
            elif current_section == "expectedResults" and line:
                test_case["expectedResults"] += line + "\n"
        
        # Clean up any extra whitespace
        for key in test_case:
            if isinstance(test_case[key], str):
                test_case[key] = test_case[key].strip()
        
        # Ensure test case has a valid ID
        if not test_case["id"] or test_case["id"].startswith('**'):
            from datetime import datetime
            test_case["id"] = f"TC-ENV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
        return test_case
    
    def upload_test_case(self, test_case):
        """
        Upload a test case with its embedding to Azure Cognitive Search.
        Simplified for ID, Title, Steps, and Expected Results only.
        
        Args:
            test_case (dict): The test case document with required fields
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure the test case has an ID
            if not test_case.get("id"):
                test_case["id"] = f"TC-ENV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Clean the ID to ensure it's valid
            test_case["id"] = ''.join(c for c in test_case["id"] if c.isalnum() or c in ['-', '_', '='])
            
            # Validate test case has required content
            if not test_case.get("title") or not test_case.get("steps") or not test_case.get("expectedResults"):
                print(f"Skipping upload for test case ID {test_case.get('id')} - missing required fields")
                return False
            
            # Ensure createdDate exists
            if not test_case.get("createdDate"):
                test_case["createdDate"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Extract content to generate embedding
            content_for_embedding = f"{test_case.get('title', '')} {test_case.get('steps', '')} {test_case.get('expectedResults', '')}"
            
            # Generate embedding
            embedding = self.generate_embedding(content_for_embedding)
            
            if not embedding:
                print(f"Failed to generate embedding for test case: {test_case.get('id')}")
                return False
            
            # Add embedding to the test case document
            test_case["vector"] = embedding
            
            # Upload to Azure Cognitive Search
            try:
                self.search_client.upload_documents(documents=[test_case])
                print(f"Successfully uploaded test case: {test_case.get('id')}")
                return True
            except Exception as e:
                print(f"Error uploading test case: {str(e)}")
                return False
        except Exception as e:
            print(f"Unexpected error in upload_test_case: {str(e)}")
            return False
    
    def parse_test_case_from_text(self, text):
        """
        Parse a test case from generated text output.
        Updated to handle Markdown formatting with asterisks.
        
        Args:
            text (str): The generated test case text
            
        Returns:
            dict: Structured test case
        """
        # Simple parsing based on simplified format
        lines = text.strip().split('\n')
        test_case = {
            "id": "",
            "title": "",
            "steps": "",
            "expectedResults": "",
            "createdDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # Ensure this is always set
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Remove Markdown bold formatting (** **)
            line = line.replace('**', '')
            
            # Check for headers - with or without asterisks
            if "Test Case ID:" in line or "ID:" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    # Clean ID value - remove any invalid characters
                    raw_id = parts[1].strip()
                    # Remove any remaining asterisks and other invalid characters
                    clean_id = ''.join(c for c in raw_id if c.isalnum() or c in ['-', '_', '='])
                    test_case["id"] = clean_id
            elif "Test Case Title:" in line or "Title:" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    test_case["title"] = parts[1].strip()
            elif "Test Steps:" in line or "Steps:" in line:
                current_section = "steps"
                test_case["steps"] = ""
            elif "Expected Results:" in line or "Expected Result:" in line:
                current_section = "expectedResults"
                test_case["expectedResults"] = ""
                
                # NEW: Also capture expected results on the same line
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        test_case["expectedResults"] = parts[1].strip() + "\n"
            elif current_section == "steps" and line:
                # Check if this line might be the Expected Results header without catching it above
                if "Expected Results:" in line or "Expected Result:" in line:
                    current_section = "expectedResults"
                    test_case["expectedResults"] = ""
                    
                    # NEW: Also capture expected results on the same line
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            test_case["expectedResults"] = parts[1].strip() + "\n"
                else:
                    test_case["steps"] += line + "\n"
            elif current_section == "expectedResults" and line:
                test_case["expectedResults"] += line + "\n"
        
        # Clean up any extra whitespace
        for key in test_case:
            if isinstance(test_case[key], str):
                test_case[key] = test_case[key].strip()
        
        # Ensure test case has a valid ID
        if not test_case["id"] or test_case["id"].startswith('**'):
            test_case["id"] = f"TC-ENV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
        # Add debug output
        print(f"Parsed test case - ID: {test_case['id']}")
        print(f"Title: '{test_case['title']}'")
        print(f"Steps length: {len(test_case['steps'])}")
        print(f"Expected Results length: {len(test_case['expectedResults'])}")
        print(f"Expected Results: '{test_case['expectedResults']}'")
        
        return test_case

    def search_similar_test_cases(self, query_text, top=3):
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query_text)
            if not query_embedding:
                print("Failed to generate embedding for query")
                return []

            # Use a dictionary approach instead of VectorQuery object directly
            # This bypasses the attribute validation issues
            vector_query_dict = {
                "kind": "vector",  # Put kind first to ensure it's processed
                "vector": query_embedding,
                "fields": "vector"
            }

            # Perform search with the dictionary (not trying to convert to VectorQuery object)
            try:
                results = self.search_client.search(
                    search_text=None,
                    vector_queries=[vector_query_dict],  # Pass dictionary directly
                    top=top,
                    select=["id", "title", "steps", "expectedResults"]
                )
                
                similar_cases = [doc for doc in results]
                return similar_cases
            except Exception as specific_e:
                print(f"Specific search error: {specific_e}")
                # If search fails, return empty list
                return []

        except Exception as e:
            print(f"Error performing vector search: {str(e)}")
            return []


# Example usage - only runs if script is executed directly
if __name__ == "__main__":
    # Test the embeddings generator
    generator = EmbeddingsGenerator()
    
    # Example test case
    test_case = {
        "id": "TC-ENV-001",
        "title": "Verify user can create a Native environment",
        "steps": "1. Navigate to Environment Management\n2. Click Create Environment\n3. Enter environment name\n4. Leave URL field empty\n5. Click Save",
        "expectedResults": "Environment should be created successfully with Native tag",
        "createdDate": "2025-03-21T00:00:00Z"
    }
    
    # Upload the test case
    result = generator.upload_test_case(test_case)
    print(f"Upload result: {result}")
    
    # Search for similar test cases
    similar = generator.search_similar_test_cases("create environment")
    print(f"Found {len(similar)} similar test cases")
    for case in similar:
        print(f"ID: {case['id']}, Title: {case['title']}")