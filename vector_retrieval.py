import asyncio
from generate_embeddings import EmbeddingsGenerator

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
    
    async def store_generated_test_case(self, test_case_text):
        """
        Parse and store a generated test case in the vector database.
        
        Args:
            test_case_text (str): The generated test case text
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Parse the test case text into a structured format
        parsed_test_case = self.embeddings_generator.parse_test_case_from_text(test_case_text)
        
        # Upload to the vector database
        return self.embeddings_generator.upload_test_case(parsed_test_case)

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