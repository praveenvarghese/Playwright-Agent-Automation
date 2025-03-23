import asyncio
from src.vector_search.embeddings import EmbeddingsGenerator

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


        """
        Analyze criteria coverage by existing test cases.
        Identifies criteria that need additional test cases.
        
        Args:
            feature_id (str): The feature ID
            criteria_objects (list): List of criteria objects
            
        Returns:
            dict: Analysis of criteria coverage
        """
        # Get all test cases for this feature
        test_cases = await self.retrieve_test_cases_by_feature_id(feature_id)
        
        # Initialize coverage counters for each criteria
        coverage = {}
        for criteria in criteria_objects:
            if criteria.get("status", "Active") == "Active":  # Only active criteria
                criteria_id = criteria.get("id")
                if criteria_id:
                    coverage[criteria_id] = {
                        "id": criteria_id,
                        "description": criteria.get("description", ""),
                        "test_cases": [],
                        "count": 0
                    }
        
        # Count test cases for each criteria
        for test_case in test_cases:
            test_case_id = test_case.get("id")
            criteria_metadata = test_case.get("criteriaMetadata", []) or []
            
            for criteria in criteria_metadata:
                criteria_id = criteria.get("criteriaId")
                if criteria_id in coverage:
                    coverage[criteria_id]["test_cases"].append(test_case_id)
                    coverage[criteria_id]["count"] += 1
        
        # Identify criteria with insufficient coverage
        insufficient_coverage = []
        for criteria_id, data in coverage.items():
            if data["count"] < 2:  # Assuming we want at least 2 test cases per criteria
                insufficient_coverage.append(data)
        
        return {
            "coverage": coverage,
            "insufficient_coverage": insufficient_coverage,
            "total_criteria": len(coverage),
            "total_test_cases": len(test_cases)
        }

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

    async def analyze_criteria_coverage(self, feature_id, criteria_objects):
        """
        Analyze criteria coverage by existing test cases.
        Identifies criteria that need additional test cases.
        
        Args:
            feature_id (str): The feature ID
            criteria_objects (list): List of criteria objects
            
        Returns:
            dict: Analysis of criteria coverage
        """
        # Get all test cases for this feature
        test_cases = await self.retrieve_test_cases_by_feature_id(feature_id)
        
        # Initialize coverage counters for each criteria
        coverage = {}
        for criteria in criteria_objects:
            if criteria.get("status", "Active") == "Active":  # Only active criteria
                criteria_id = criteria.get("id")
                if criteria_id:
                    coverage[criteria_id] = {
                        "id": criteria_id,
                        "description": criteria.get("description", ""),
                        "test_cases": [],
                        "count": 0
                    }
        
        # Count test cases for each criteria
        for test_case in test_cases:
            test_case_id = test_case.get("id")
            criteria_metadata = test_case.get("criteriaMetadata", []) or []
            
            for criteria in criteria_metadata:
                criteria_id = criteria.get("criteriaId")
                # Only count active criteria references
                if criteria_id in coverage and criteria.get("status", "Active") == "Active":
                    coverage[criteria_id]["test_cases"].append(test_case_id)
                    coverage[criteria_id]["count"] += 1
        
        # Identify criteria with insufficient coverage
        insufficient_coverage = []
        for criteria_id, data in coverage.items():
            if data["count"] < 2:  # Assuming we want at least 2 test cases per criteria
                insufficient_coverage.append(data)
        
        return {
            "coverage": coverage,
            "insufficient_coverage": insufficient_coverage,
            "total_criteria": len(coverage),
            "total_test_cases": len(test_cases)
        }

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