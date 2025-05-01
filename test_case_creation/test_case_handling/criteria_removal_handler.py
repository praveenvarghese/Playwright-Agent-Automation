import os
import json
import re
from datetime import datetime, timezone
import traceback
from test_case_creation.config.config import TestCaseCritic, TestCaseOptimizer
from test_case_creation.data_services.embeddings import EmbeddingsGenerator
from test_case_creation.helpers.common_utils import print_progress, print_success, print_warning, print_error
from test_case_creation.data_services.vector_search import VectorRetrievalSystem
from test_case_creation.feature_management.feature_processor import FeatureProcessor

# Define paths for prompt files
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PROMPTS_DIR = os.path.join(PROJECT_ROOT, "test_case_creation", "prompts")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

# Create directories if they don't exist
for directory in [LOGS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

# Paths for the new prompt files
REMOVAL_CRITIC_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_removal_critic_prompt.txt")
REMOVAL_OPTIMIZER_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_removal_optimizer_prompt.txt")

def parse_critic_action(critique_text):
    """Parse the critique response to determine recommended action."""
    # Look for the RECOMMENDED ACTION line
    action_match = re.search(r'RECOMMENDED ACTION:\s*(KEEP|UPDATE|REGENERATE)', critique_text, re.IGNORECASE)
    
    if action_match:
        action = action_match.group(1).upper()
        if action == "KEEP":
            return "Keep"
        elif action == "UPDATE":
            return "Update"
        else:
            return "Regenerate"
    
    # Fallback parsing if no explicit recommendation found
    if "should be kept" in critique_text.lower() or "keep as is" in critique_text.lower():
        return "Keep"
    elif "should be updated" in critique_text.lower() or "needs updates" in critique_text.lower():
        return "Update"
    else:
        return "Regenerate"  # Default to regenerate if unclear

async def mark_deprecated_criteria_in_test_cases_with_critique(feature_id, removed_criteria_ids, criteria_map=None):
    """
    Enhanced version that uses critique and optimizer flow for handling removed criteria.
    
    Args:
        feature_id (str): The feature ID
        removed_criteria_ids (list): List of criteria IDs that were removed
        criteria_map (dict): Optional mapping of criteria IDs to their details
        
    Returns:
        dict: Summary of actions taken
    """
    if not removed_criteria_ids:
        print_progress("No criteria were removed, no cleanup needed")
        return {
            "kept": 0,
            "updated": 0,
            "regenerated": 0,
            "errors": 0
        }
        
    print_progress(f"Using enhanced AI critique flow for {len(removed_criteria_ids)} removed criteria")
    print_progress(f"Criteria IDs to analyze: {', '.join(removed_criteria_ids)}")
    
    # Initialize components
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    feature_processor = FeatureProcessor()
    
    # Get criteria details if not provided
    if criteria_map is None:
        # Get all criteria for this feature
        feature_results = list(feature_processor.search_client.search(
            search_text="",
            filter=f"id eq '{feature_id}'",
            select=["acceptanceCriteria"]
        ))
        
        if not feature_results or not feature_results[0].get("acceptanceCriteria"):
            print_warning(f"Could not find criteria details for feature {feature_id}")
            criteria_map = {}
        else:
            # Create mapping of criteria IDs to details
            criteria_list = feature_results[0].get("acceptanceCriteria", [])
            criteria_map = {c.get("id"): c for c in criteria_list if c.get("id")}
    
    # Load prompt templates
    try:
        with open(REMOVAL_CRITIC_PROMPT_FILE, "r", encoding="utf-8") as f:
            critic_template = f.read()
            
        with open(REMOVAL_OPTIMIZER_PROMPT_FILE, "r", encoding="utf-8") as f:
            optimizer_template = f.read()
    except FileNotFoundError as e:
        print_error(f"Error loading prompt templates: {str(e)}")
        return {
            "kept": 0,
            "updated": 0,
            "regenerated": 0,
            "errors": 1
        }
    
    # Get test cases to process
    test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    
    print_progress(f"Analyzing {len(test_cases)} test cases")
    
    # Result counters
    results = {
        "kept": 0,
        "updated": 0,
        "regenerated": 0,
        "errors": 0
    }
    
    # Process each test case
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        if not test_case_id:
            print_warning(f"Test case missing ID, skipping")
            continue
            
        # Skip inactive test cases
        if test_case.get("status") == "Inactive":
            print_progress(f"Skipping inactive test case {test_case_id}")
            continue
            
        # Get current criteria metadata
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        if not criteria_metadata:
            print_progress(f"Test case {test_case_id} has no criteria metadata, skipping")
            continue
        
        # Separate the removed and remaining criteria for this test case
        removed_criteria_for_tc = []
        remaining_criteria_for_tc = []
        
        for criteria in criteria_metadata:
            criteria_id = criteria.get("criteriaId")
            if not criteria_id:
                continue
                
            if criteria_id in removed_criteria_ids:
                removed_criteria_for_tc.append(criteria)
            else:
                remaining_criteria_for_tc.append(criteria)
        
        # If no removed criteria affect this test case, skip it
        if not removed_criteria_for_tc:
            print_progress(f"Test case {test_case_id} is not affected by removed criteria, skipping")
            continue
            
        print_progress(f"Analyzing test case {test_case_id} affected by {len(removed_criteria_for_tc)} removed criteria")
        
        # Prepare JSON representations for the prompt
        test_case_json = json.dumps({
            "id": test_case.get("id", ""),
            "title": test_case.get("title", ""),
            "steps": test_case.get("steps", ""),
            "expectedResults": test_case.get("expectedResults", "")
        }, indent=2)
        
        removed_criteria_json = json.dumps(removed_criteria_for_tc, indent=2)
        remaining_criteria_json = json.dumps(remaining_criteria_for_tc, indent=2)
        
        # Prepare the critique prompt
        critique_prompt = critic_template
        critique_prompt = critique_prompt.replace("{test_case_json}", test_case_json)
        critique_prompt = critique_prompt.replace("{removed_criteria_json}", removed_criteria_json)
        critique_prompt = critique_prompt.replace("{remaining_criteria_json}", remaining_criteria_json)
        
        try:
            # Get critique from TestCaseCritic
            critique = await TestCaseCritic.a_generate_reply(
                messages=[{"role": "user", "content": critique_prompt}]
            )
            
            # Save critique for debugging
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            critique_file = os.path.join(LOGS_DIR, f"RemovalCritique_{test_case_id}_{timestamp}.txt")
            with open(critique_file, "w", encoding="utf-8") as f:
                f.write(critique)
            
            # Parse the recommended action
            action = parse_critic_action(critique)
            print_progress(f"AI recommends: {action} for test case {test_case_id}")
            
            if action == "Keep":
                # Keep the test case, but mark removed criteria as inactive
                updated_test_case = dict(test_case)
                updated_criteria_metadata = []
                
                for criteria in criteria_metadata:
                    criteria_id = criteria.get("criteriaId")
                    if criteria_id in removed_criteria_ids:
                        # Mark removed criteria as inactive
                        updated_criteria = dict(criteria)
                        updated_criteria["status"] = "Inactive"
                        updated_criteria["removedDate"] = datetime.now(timezone.utc).isoformat()
                        updated_criteria_metadata.append(updated_criteria)
                    else:
                        # Keep active criteria as is
                        updated_criteria_metadata.append(dict(criteria))
                
                updated_test_case["criteriaMetadata"] = updated_criteria_metadata
                
                # Update in database
                success = embeddings_generator.upload_test_case(updated_test_case)
                
                if success:
                    results["kept"] += 1
                    print_success(f"Test case {test_case_id} kept with inactive criteria references")
                else:
                    results["errors"] += 1
                    print_warning(f"Failed to update test case {test_case_id}")
                    
            elif action == "Update":
                # Prepare optimizer prompt
                optimizer_prompt = optimizer_template
                optimizer_prompt = optimizer_prompt.replace("{test_case_json}", test_case_json)
                optimizer_prompt = optimizer_prompt.replace("{removed_criteria_json}", removed_criteria_json)
                optimizer_prompt = optimizer_prompt.replace("{remaining_criteria_json}", remaining_criteria_json)
                optimizer_prompt = optimizer_prompt.replace("{critique}", critique)
                optimizer_prompt = optimizer_prompt.replace("{test_case_id}", test_case_id)
                
                # Get optimized test case
                optimized_response = await TestCaseOptimizer.a_generate_reply(
                    messages=[{"role": "user", "content": optimizer_prompt}]
                )
                
                # Save optimizer response for debugging
                optimizer_file = os.path.join(LOGS_DIR, f"RemovalOptimizer_{test_case_id}_{timestamp}.txt")
                with open(optimizer_file, "w", encoding="utf-8") as f:
                    f.write(optimized_response)
                
                # Extract JSON from response
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', optimized_response)
                if not json_match:
                    json_match = re.search(r'(\{[\s\S]*?\})', optimized_response)
                
                if json_match:
                    optimized_json = json_match.group(1).strip()
                    
                    try:
                        # Parse the updated test case
                        updated_tc = json.loads(optimized_json)
                        
                        # Preserve original metadata
                        updated_test_case = dict(test_case)
                        updated_test_case["title"] = updated_tc.get("title", test_case.get("title", ""))
                        updated_test_case["steps"] = updated_tc.get("steps", test_case.get("steps", ""))
                        updated_test_case["expectedResults"] = updated_tc.get("expectedResults", test_case.get("expectedResults", ""))
                        
                        if isinstance(updated_tc.get("steps"), list):
                            updated_tc["steps"] = "\n".join(updated_tc.get("steps"))

                        # Same for expected results
                        if isinstance(updated_tc.get("expectedResults"), list):
                            updated_tc["expectedResults"] = "\n".join(updated_tc.get("expectedResults"))
                            
                        # Update criteria metadata
                        updated_criteria_metadata = []
                        for criteria in criteria_metadata:
                            criteria_id = criteria.get("criteriaId")
                            if criteria_id in removed_criteria_ids:
                                # Mark removed criteria as inactive
                                updated_criteria = dict(criteria)
                                updated_criteria["status"] = "Inactive"
                                updated_criteria["removedDate"] = datetime.now(timezone.utc).isoformat()
                                updated_criteria_metadata.append(updated_criteria)
                            else:
                                # Keep active criteria as is
                                updated_criteria_metadata.append(dict(criteria))
                        
                        updated_test_case["criteriaMetadata"] = updated_criteria_metadata
                        
                        # Update in database
                        success = embeddings_generator.upload_test_case(updated_test_case)
                        
                        if success:
                            results["updated"] += 1
                            print_success(f"Successfully updated test case {test_case_id}")
                        else:
                            results["errors"] += 1
                            print_warning(f"Failed to update test case {test_case_id}")
                            
                    except json.JSONDecodeError:
                        results["errors"] += 1
                        print_warning(f"Failed to parse JSON for test case {test_case_id}")
                else:
                    results["errors"] += 1
                    print_warning(f"Could not extract JSON from optimizer response for {test_case_id}")
            
            else:  # Regenerate
                # Mark the test case as inactive
                updated_test_case = dict(test_case)
                updated_test_case["status"] = "Inactive"
                
                if "statusReason" in updated_test_case:
                    updated_test_case["statusReason"] = "Criteria removed - AI recommended regeneration"
                
                # Update in database
                success = embeddings_generator.upload_test_case(updated_test_case)
                
                if success:
                    results["regenerated"] += 1
                    print_success(f"Marked test case {test_case_id} as inactive for regeneration")
                else:
                    results["errors"] += 1
                    print_warning(f"Failed to update status for test case {test_case_id}")
                
        except Exception as e:
            results["errors"] += 1
            print_error(f"Error processing test case {test_case_id}: {str(e)}")
            traceback.print_exc()
    
    # Print summary
    print_success(f"Processed {len(test_cases)} test cases:")
    print_success(f"  - Kept: {results['kept']}")
    print_success(f"  - Updated: {results['updated']}")
    print_success(f"  - Marked for regeneration: {results['regenerated']}")
    print_success(f"  - Errors: {results['errors']}")
    
    return results