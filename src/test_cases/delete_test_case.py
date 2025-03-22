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


class FeatureDeleter:
    def __init__(self):
        """
        Initialize the feature deleter with Azure Cognitive Search configuration.
        """
        # Load environment variables
        load_dotenv()
        
        # Azure Cognitive Search Configuration
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_FEATURE_INDEX", "features-index")
        
        # Initialize Search client
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.search_key)
        )
    
    def delete_feature(self, feature_id):
        """
        Delete a feature from the search index by ID.
        
        Args:
            feature_id (str): The ID of the feature to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.search_client.delete_documents(documents=[{"id": feature_id}])
            print(f"Successfully deleted feature: {feature_id}")
            return True
        except Exception as e:
            print(f"Error deleting feature: {str(e)}")
            return False
    
    def search_feature(self, feature_id):
        """
        Search for a feature by ID to verify it exists.
        
        Args:
            feature_id (str): The ID of the feature to search for
            
        Returns:
            dict: The feature document or None if not found
        """
        try:
            # Use the get_document method to retrieve a document by ID
            result = self.search_client.get_document(key=feature_id)
            print(f"Found feature: {result.get('id', 'Unknown')}, Name: {result.get('name', 'Unknown')}")
            return result
        except Exception as e:
            print(f"Error searching for feature: {str(e)}")
            return None
    
    def list_all_features(self, max_results=100):
        """
        List all features in the index.
        
        Args:
            max_results (int): Maximum number of results to return
            
        Returns:
            list: All features in the index
        """
        try:
            results = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=max_results,
                select=["id", "name"]
            )
            
            features = list(results)
            print(f"Found {len(features)} features:")
            for i, feature in enumerate(features):
                print(f"{i+1}. ID: {feature.get('id', 'Unknown')}, Name: {feature.get('name', 'Unknown')}")
            
            return features
        except Exception as e:
            print(f"Error listing features: {str(e)}")
            return []

    def delete_all_features(self):
        """
        Delete all features from the Azure Cognitive Search index.
        
        Returns:
            int: Number of features deleted
        """
        try:
            # First, get confirmation from the user
            confirm = input("Are you sure you want to delete ALL features? This cannot be undone. (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled.")
                return 0
                
            results = self.search_client.search(
                search_text="*",
                select=["id"]
            )
            documents = [{"id": doc["id"]} for doc in results]

            if not documents:
                print("No features found to delete.")
                return 0

            self.search_client.delete_documents(documents=documents)
            print(f"Successfully deleted {len(documents)} features.")
            return len(documents)
        except Exception as e:
            print(f"Error deleting all features: {str(e)}")
        return 0


def show_menu():
    """Display the main menu."""
    print("\n=== Test Case & Feature Management ===")
    print("1. Delete a test case by ID")
    print("2. List all test cases")
    print("3. Search for a test case by ID")
    print("4. Delete a feature by ID")
    print("5. List all features")
    print("6. Search for a feature by ID")
    print("7. Delete all test cases")
    print("8. Delete all features")
    print("9. Exit")
    return input("Select an option (1-9): ")

async def main():
    """Main function to run the test case and feature deleter."""
    test_case_deleter = TestCaseDeleter()
    feature_deleter = FeatureDeleter()
    
    if len(sys.argv) > 1:
        # Test case operations
        if sys.argv[1] == "delete-all-testcases":
            test_case_deleter.delete_all_test_cases()
        elif sys.argv[1] == "delete-testcase" and len(sys.argv) > 2:
            test_case_id = sys.argv[2]
            test_case_deleter.delete_test_case(test_case_id)
        elif sys.argv[1] == "list-testcases":
            test_case_deleter.list_all_test_cases()
        elif sys.argv[1] == "search-testcase" and len(sys.argv) > 2:
            test_case_id = sys.argv[2]
            test_case_deleter.search_test_case(test_case_id)
        
        # Feature operations
        elif sys.argv[1] == "delete-all-features":
            feature_deleter.delete_all_features()
        elif sys.argv[1] == "delete-feature" and len(sys.argv) > 2:
            feature_id = sys.argv[2]
            feature_deleter.delete_feature(feature_id)
        elif sys.argv[1] == "list-features":
            feature_deleter.list_all_features()
        elif sys.argv[1] == "search-feature" and len(sys.argv) > 2:
            feature_id = sys.argv[2]
            feature_deleter.search_feature(feature_id)
        
        # Interactive mode
        elif sys.argv[1] == "interactive":
            while True:
                choice = show_menu()
                
                if choice == "1":
                    test_case_id = input("Enter test case ID to delete: ")
                    test_case_deleter.delete_test_case(test_case_id)
                elif choice == "2":
                    test_case_deleter.list_all_test_cases()
                elif choice == "3":
                    test_case_id = input("Enter test case ID to search: ")
                    test_case_deleter.search_test_case(test_case_id)
                elif choice == "4":
                    feature_id = input("Enter feature ID to delete: ")
                    feature_deleter.delete_feature(feature_id)
                elif choice == "5":
                    feature_deleter.list_all_features()
                elif choice == "6":
                    feature_id = input("Enter feature ID to search: ")
                    feature_deleter.search_feature(feature_id)
                elif choice == "7":
                    test_case_deleter.delete_all_test_cases()
                elif choice == "8":
                    feature_deleter.delete_all_features()
                elif choice == "9":
                    print("Exiting...")
                    break
                else:
                    print("Invalid choice. Please try again.")
                
                input("\nPress Enter to continue...")
        
        else:
            print_usage()
    else:
        print_usage()

def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print("  python delete_feature_case.py interactive")
    print("  python delete_feature_case.py delete-testcase <test_case_id>")
    print("  python delete_feature_case.py delete-all-testcases")
    print("  python delete_feature_case.py list-testcases")
    print("  python delete_feature_case.py search-testcase <test_case_id>")
    print("  python delete_feature_case.py delete-feature <feature_id>")
    print("  python delete_feature_case.py delete-all-features")
    print("  python delete_feature_case.py list-features")
    print("  python delete_feature_case.py search-feature <feature_id>")

if __name__ == "__main__":
    asyncio.run(main())