import asyncio
from src.core.test_case_workflow import read_feature_requirement, read_requirement, find_similar_test_cases, create_test_cases, process_and_store_test_cases
from src.core.test_case_workflow import print_success, print_error
from src.utils.logging_filter import configure_clean_console

async def main():
    """Main workflow for test case generation and storage."""
    # Configure clean console output - filter out library logs
    configure_clean_console()
    
    try:
        # Step 1: Read and process the feature requirement
        feature_data = await read_feature_requirement()
        
        # Step 2: Read the test case requirement
        requirement_text = await read_requirement()
        if not requirement_text:
            return
        
        # Step 3: Find similar test cases for context
        similar_cases = await find_similar_test_cases(requirement_text)
        
        # Step 4: Generate new test cases
        test_cases_content = await create_test_cases(similar_cases)
        
        # Step 5: Process and store the test cases with feature relation
        if test_cases_content:
            await process_and_store_test_cases(test_cases_content, feature_data)
        
        print_success("Workflow completed successfully!")
        
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())