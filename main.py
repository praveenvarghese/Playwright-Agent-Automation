import asyncio
import os
from src.core.test_case_workflow import read_feature_requirement, read_requirement, find_similar_test_cases, create_test_cases, process_and_store_test_cases
from src.core.test_case_workflow import print_success, print_error, print_progress, print_warning
from src.utils.logging_filter import configure_clean_console
from src.feature_update.feature_update_workflow import update_feature_workflow  # Import the new module

async def main():
    """Enhanced main workflow for test case generation and storage with update support."""
    # Configure clean console output - filter out library logs
    configure_clean_console()
    
    try:
        # Step 1: Read and process the feature requirement
        feature_data = await read_feature_requirement()
        if not feature_data:
            print_error("Failed to read feature requirement")
            return
            
        print_progress(f"Processing feature: {feature_data.get('title', 'Unknown')}")
        print_progress(f"Feature type: {feature_data.get('type', 'Unknown')}")
            
        # Check if this is an update operation
        if feature_data.get('type', '').upper() == 'UPDATE':
            print_progress("This is a feature update. Using enhanced update workflow...")
            
            # Use the enhanced update workflow
            update_success = await update_feature_workflow(feature_data)
            
            if update_success:
                print_success("Feature update workflow completed successfully!")
                return
            else:
                print_warning("Feature update workflow did not complete. Falling back to standard workflow.")
                # Continue with standard workflow as fallback
        
        # Standard workflow for new features or fallback from update
        # Step 2: Read the test case requirement
        requirement_text = await read_requirement()
        if not requirement_text:
            print_error("Failed to read test case requirement")
            return
        
        # Step 3: Find similar test cases for context
        similar_cases = await find_similar_test_cases(requirement_text)
        
        # Step 4: Generate new test cases
        test_cases_content = await create_test_cases(similar_cases)
        
        # Step 5: Process and store the test cases with feature relation
        if test_cases_content:
            await process_and_store_test_cases(test_cases_content, feature_data)
        else:
            print_error("No test cases were generated")
        
        print_success("Workflow completed successfully!")
        
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")
        # Log the full error with traceback
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())