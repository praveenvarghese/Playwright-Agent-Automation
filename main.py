import asyncio
from src.core.test_case_workflow import read_requirement, find_similar_test_cases, create_test_cases, process_and_store_test_cases
from src.core.test_case_workflow import print_success, print_error
from src.utils.logging_filter import configure_clean_console

async def main():
    """Main workflow for test case generation and storage."""
    # Configure clean console output - filter out library logs
    configure_clean_console()
    
    try:
        # Step 1: Read the requirement
        requirement_text = await read_requirement()
        if not requirement_text:
            return
        
        # Step 2: Find similar test cases for context
        similar_cases = await find_similar_test_cases(requirement_text)
        
        # Step 3: Generate new test cases
        test_cases_content = await create_test_cases(similar_cases)
        
        # Step 4: Process and store the test cases
        if test_cases_content:
            await process_and_store_test_cases(test_cases_content)
        
        print_success("Workflow completed successfully!")
        
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())