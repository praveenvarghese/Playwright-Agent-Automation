import os
import sys
import asyncio
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

class TestCaseDeleter:
    def __init__(self):
        """
        Initialize the test case deleter with Azure Cognitive Search configuration.
        """
        # Load environment variables
        load_dotenv()
        
        # Azure Cognitive Search Configuration
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "testcases-vector-index")
        
        # Initialize Search client
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.search_key)
        )
    
    def delete_test_case(self, test_case_id):
        """
        Delete a test case from the search index by ID.
        
        Args:
            test_case_id (str): The ID of the test case to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.search_client.delete_documents(documents=[{"id": test_case_id}])
            print(f"Successfully deleted test case: {test_case_id}")
            return True
        except Exception as e:
            print(f"Error deleting test case: {str(e)}")
            return False
    
    def search_test_case(self, test_case_id):
        """
        Search for a test case by ID to verify it exists.
        
        Args:
            test_case_id (str): The ID of the test case to search for
            
        Returns:
            dict: The test case document or None if not found
        """
        try:
            # Use the get_document method to retrieve a document by ID
            result = self.search_client.get_document(key=test_case_id)
            print(f"Found test case: {result.get('id', 'Unknown')}, Title: {result.get('title', 'Unknown')}")
            return result
        except Exception as e:
            print(f"Error searching for test case: {str(e)}")
            return None
    
    def list_all_test_cases(self, max_results=100):
        """
        List all test cases in the index.
        
        Args:
            max_results (int): Maximum number of results to return
            
        Returns:
            list: All test cases in the index
        """
        try:
            results = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=max_results,
                select=["id", "title"]
            )
            
            test_cases = list(results)
            print(f"Found {len(test_cases)} test cases:")
            for i, case in enumerate(test_cases):
                print(f"{i+1}. ID: {case.get('id', 'Unknown')}, Title: {case.get('title', 'Unknown')}")
            
            return test_cases
        except Exception as e:
            print(f"Error listing test cases: {str(e)}")
            return []

    def delete_all_test_cases(self):
        """
        Delete all test cases from the Azure Cognitive Search index.
        
        Returns:
            int: Number of test cases deleted
        """
        try:
            results = self.search_client.search(
                search_text="*",
                select=["id"]
            )
            documents = [{"id": doc["id"]} for doc in results]

            if not documents:
                print("No test cases found to delete.")
                return 0

            self.search_client.delete_documents(documents=documents)
            print(f"Successfully deleted {len(documents)} test cases.")
            return len(documents)
        except Exception as e:
            print(f"Error deleting all test cases: {str(e)}")
        return 0


def show_menu():
    """Display the main menu."""
    print("\n=== Test Case Management ===")
    print("1. Delete a test case by ID")
    print("2. List all test cases")
    print("3. Search for a test case by ID")
    print("4. Exit")
    return input("Select an option (1-4): ")

async def main():
    """Main function to run the test case deleter."""
    deleter = TestCaseDeleter()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "delete-all":
            deleter.delete_all_test_cases()
        elif sys.argv[1] == "delete" and len(sys.argv) > 2:
            test_case_id = sys.argv[2]
            deleter.delete_test_case(test_case_id)
        elif sys.argv[1] == "list":
            deleter.list_all_test_cases()
        elif sys.argv[1] == "search" and len(sys.argv) > 2:
            test_case_id = sys.argv[2]
            deleter.search_test_case(test_case_id)
        else:
            print("Usage:")
            print("  python delete_test_case.py delete <test_case_id>")
            print("  python delete_test_case.py delete-all")
            print("  python delete_test_case.py list")
            print("  python delete_test_case.py search <test_case_id>")
    else:
        print("Usage:")
        print("  python delete_test_case.py delete <test_case_id>")
        print("  python delete_test_case.py delete-all")
        print("  python delete_test_case.py list")
        print("  python delete_test_case.py search <test_case_id>")

if __name__ == "__main__":
    asyncio.run(main())