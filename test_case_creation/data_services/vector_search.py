import asyncio
from test_case_creation.data_services.embeddings import EmbeddingsGenerator

class VectorRetrievalSystem:
    def __init__(self):
        """
        Initialize the vector retrieval system.
        """
        self.embeddings_generator = EmbeddingsGenerator()
    
    async def retrieve_similar_test_cases(self, requirement_text, top=3):
        """
        Retrieve similar test cases based on a requirement.
        
        Args:
            requirement_text (str): The requirement text
            top (int): Number of results to return
            
        Returns:
            list: Similar test cases
        """
        return self.embeddings_generator.search_similar_test_cases(requirement_text, top=top)
    
    # Add these methods to your VectorRetrievalSystem class in retrieval.py

    async def retrieve_test_cases_by_feature_id(self, feature_id, limit=100):
        """
        Retrieve test cases associated with a specific feature ID.
        
        Args:
            feature_id (str): The feature ID to search for
            limit (int): Maximum number of results to return
            
        Returns:
            list: Test cases associated with the feature
        """
        # Create a filter to find test cases with matching feature ID
        filter_str = f"featureMetadata/featureId eq '{feature_id}'"
        
        try:
            # Search using the filter
            results = list(self.embeddings_generator.search_client.search(
                search_text="*",  # Search all
                filter=filter_str,
                select=["id", "title", "steps", "expectedResults", "criteriaMetadata"],
                top=limit
            ))
            
            print(f"Found {len(results)} test cases for feature ID {feature_id}")
            return results
        except Exception as e:
            print(f"Error retrieving test cases for feature {feature_id}: {str(e)}")
            return []

# Example usage
async def example_usage():
    retrieval_system = VectorRetrievalSystem()
    
    # Example requirement
    requirement = "Users should be able to delete environments after confirmation."
    
    # Retrieve similar test cases
    similar_cases = await retrieval_system.retrieve_similar_test_cases(requirement)
    print(f"Found {len(similar_cases)} similar test cases")
    
    for case in similar_cases:
        print(f"ID: {case['id']}, Title: {case['title']}")

if __name__ == "__main__":
    asyncio.run(example_usage())