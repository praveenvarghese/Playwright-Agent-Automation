import asyncio
import os
import re
from src.core.test_case_workflow import read_feature_requirement, read_requirement, find_similar_test_cases, create_test_cases, process_and_store_test_cases
from src.core.test_case_workflow import print_success, print_error, print_progress, print_warning
from src.utils.logging_filter import configure_clean_console
from src.feature_update.feature_update_workflow import update_feature_workflow  # Import the existing module
from src.feature_update.feature_update_workflow import read_tagged_feature_requirement, tagged_update_feature_workflow  # Import the new functions

async def main():
    """Enhanced main workflow for test case generation and storage with update support."""
    # Configure clean console output - filter out library logs
    configure_clean_console()
    
    try:
        # Step 1: Read and process the feature requirement
        # Check if the feature uses tagged format
        feature_file = os.path.join("prompts", "feature_requirement.txt")
        
        # Check if file exists
        if not os.path.exists(feature_file):
            print_error(f"Feature requirement file not found at {feature_file}")
            return
        
        # Check if this is a tagged format
        with open(feature_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if file contains tags like [KEEP], [UPDATE], etc.
        is_tagged = re.search(r'\[(KEEP|UPDATE|NEW|REMOVE)\]', content, re.IGNORECASE) is not None
        
        # Process feature based on format
        if is_tagged:
            print_progress("Detected tagged feature format. Using enhanced parser...")
            feature_data = await read_tagged_feature_requirement(feature_file)
        else:
            print_progress("Using standard feature parser...")
            feature_data = await read_feature_requirement()
            
        if not feature_data:
            print_error("Failed to read feature requirement")
            return
            
        print_progress(f"Processing feature: {feature_data.get('title', 'Unknown')}")
        print_progress(f"Feature type: {feature_data.get('type', 'Unknown')}")
            
        # Check if this is an update operation
        if feature_data.get('type', '').upper() == 'UPDATE':
            if is_tagged:
                print_progress("This is a tagged feature update. Using new workflow...")
                
                # Use the new tagged workflow
                update_success = await tagged_update_feature_workflow(feature_data)
                
                if update_success:
                    print_success("Tagged feature update workflow completed successfully!")
                    return
                else:
                    print_warning("Tagged feature update workflow did not complete. Falling back to standard workflow.")
            else:
                print_progress("This is a feature update. Using existing update workflow...")
                
                # Use the existing update workflow
                update_success = await update_feature_workflow(feature_data)
                
                if update_success:
                    print_success("Feature update workflow completed successfully!")
                    return
                else:
                    print_warning("Feature update workflow did not complete. Falling back to standard workflow.")
        
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