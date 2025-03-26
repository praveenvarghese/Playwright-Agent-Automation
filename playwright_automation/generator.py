"""
Test script generator for Playwright POM framework.
This module handles retrieving test cases and coordinating the generation process.
"""

import os
import asyncio
from datetime import datetime

# Import from your existing project structure
from src.vector_search.retrieval import VectorRetrievalSystem
from src.vector_search.feature_processor import FeatureProcessor

# Import local modules
from .page_objects import generate_page_objects
from .script_manager import save_script, check_script_update_needed, get_test_script_path
from .prompts import get_test_script_prompt
from .utils import format_console_output


async def generate_scripts_for_feature(feature_id, force_update=False):
    """
    Generate Playwright scripts for all test cases associated with a feature.
    
    Args:
        feature_id (str): The feature ID (e.g., FEAT-ENV-001)
        force_update (bool): Whether to force regeneration of all scripts
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(format_console_output("info", f"Starting script generation for feature: {feature_id}"))
    
    try:
        # Initialize retrieval system and feature processor
        retrieval_system = VectorRetrievalSystem()
        feature_processor = FeatureProcessor()
        
        # Get feature data
        # First try to search for the feature directly in the search index
        feature_results = list(feature_processor.search_client.search(
            search_text="",
            filter=f"id eq '{feature_id}'",
            select=["*"]
        ))
        
        if not feature_results:
            print(format_console_output("error", f"Feature {feature_id} not found in search index"))
            return False
        
        feature_data = dict(feature_results[0])
        print(format_console_output("info", f"Found feature: {feature_data.get('name', 'Unknown')}"))
        
        # Get test cases for feature
        test_cases = await retrieval_system.retrieve_test_cases_by_feature_id(feature_id)
        
        if not test_cases:
            print(format_console_output("warning", f"No test cases found for feature {feature_id}"))
            return False
        
        print(format_console_output("info", f"Found {len(test_cases)} test cases for feature {feature_id}"))
        
        # Generate page objects first - this needs to be done once per feature
        # This will now use browser inspection for more accurate selectors
        page_objects = await generate_page_objects(feature_data, test_cases)
        
        # Generate test scripts for each test case
        generated_count = 0
        for test_case in test_cases:
            test_case_id = test_case.get('id')
            
            # Check if update is needed (unless forced)
            if not force_update and not check_script_update_needed(test_case):
                print(format_console_output("info", f"Script for {test_case_id} is up to date, skipping"))
                continue
            
            # Generate script
            success = await generate_script_for_test_case(
                test_case_id, 
                force_update=force_update,
                test_case_data=test_case,
                feature_data=feature_data,
                page_objects=page_objects
            )
            
            if success:
                generated_count += 1
        
        print(format_console_output("success", f"Generated/updated {generated_count} scripts for feature {feature_id}"))
        return True
        
    except Exception as e:
        print(format_console_output("error", f"Error generating scripts for feature {feature_id}: {str(e)}"))
        import traceback
        traceback.print_exc()
        return False


async def generate_script_for_test_case(test_case_id, force_update=False, test_case_data=None, 
                                        feature_data=None, page_objects=None):
    """
    Generate a Playwright test script for a single test case.
    
    Args:
        test_case_id (str): The test case ID (e.g., TC-ENV-001)
        force_update (bool): Whether to force regeneration
        test_case_data (dict): Optional pre-fetched test case data
        feature_data (dict): Optional pre-fetched feature data
        page_objects (list): Optional pre-generated page objects
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get test case data if not provided
        if test_case_data is None:
            # Initialize retrieval system
            from src.vector_search.embeddings import EmbeddingsGenerator
            embeddings_generator = EmbeddingsGenerator()
            
            # Search for test case
            tc_results = list(embeddings_generator.search_client.search(
                search_text="",
                filter=f"id eq '{test_case_id}'",
                select=["*"]
            ))
            
            if not tc_results:
                print(format_console_output("error", f"Test case {test_case_id} not found"))
                return False
                
            test_case_data = dict(tc_results[0])
            
            # Get feature data if not provided
            if feature_data is None and test_case_data.get("featureMetadata"):
                feature_id = test_case_data["featureMetadata"].get("featureId")
                
                if feature_id:
                    # Get feature data
                    feature_processor = FeatureProcessor()
                    feature_results = list(feature_processor.search_client.search(
                        search_text="",
                        filter=f"id eq '{feature_id}'",
                        select=["*"]
                    ))
                    
                    if feature_results:
                        feature_data = dict(feature_results[0])
        
        # Get feature information summary
        feature_summary = "Unknown Feature"
        if feature_data:
            feature_summary = f"{feature_data.get('name', 'Unknown Feature')} ({feature_data.get('id', 'Unknown ID')})"
        
        print(format_console_output("info", f"Generating script for test case: {test_case_id} (Feature: {feature_summary})"))
        
        # Generate page objects if not provided
        if page_objects is None and feature_data is not None:
            page_objects = await generate_page_objects(feature_data, [test_case_data])
        
        # Check if page objects are available
        if not page_objects:
            print(format_console_output("warning", "No page objects available. Using generic approach."))
            # Create a default page object list
            page_objects = ["BasePage"]
            
        # Generate the test script
        script_content = await generate_test_script_content(test_case_data, page_objects, feature_data)
        
        # Save the script
        script_path = save_script(test_case_data, script_content)
        
        if script_path:
            print(format_console_output("success", f"Generated script at: {script_path}"))
            return True
        else:
            print(format_console_output("error", f"Failed to save script for test case {test_case_id}"))
            return False
            
    except Exception as e:
        print(format_console_output("error", f"Error generating script for test case {test_case_id}: {str(e)}"))
        import traceback
        traceback.print_exc()
        return False


async def generate_test_script_content(test_case, page_objects, feature_data):
    """
    Generate the actual test script content using AI.
    
    Args:
        test_case (dict): The test case data
        page_objects (list): List of page objects to use
        feature_data (dict): The feature data
        
    Returns:
        str: The generated test script content
    """
    from .generator_agent import generate_test_script
    from .critic_agent import improve_script
    
    # Generate the initial script
    script_content = await generate_test_script(test_case, page_objects, feature_data)
    
    # Review and improve the script
    improved_script = await improve_script(test_case, script_content, page_objects)
    
    return improved_script

def generate_fallback_script(test_case):
    """Generate a basic fallback script if AI generation fails."""
    test_id = test_case.get('id', 'unknown')
    title = test_case.get('title', 'Unknown Test Case')
    steps = test_case.get('steps', 'No steps available')
    expected = test_case.get('expectedResults', 'No expected results available')
    
    return f"""// Fallback script for {test_id}: {title}
const {{ test, expect }} = require('@playwright/test');
const {{ BasePage }} = require('../pages/BasePage');

/**
 * @param {{ page: import('@playwright/test').Page }} param0
 */
test('{title}', async ({{ page }}) => {{
  // TODO: Implement this test case
  // Steps:
  /*
{steps}
  */
  
  // Expected Results:
  /*
{expected}
  */
  
  // This is a fallback implementation due to generation failure
  const basePage = new BasePage(page);
  await basePage.navigate('/');
  console.log('Test not fully implemented - fallback generated');
}});
"""