import os
import asyncio
from datetime import datetime, timezone
import json
import re
from test_case_creation.test_case_handling.generator import generate_test_cases
from test_case_creation.data_services.vector_search import VectorRetrievalSystem
from test_case_creation.data_services.embeddings import EmbeddingsGenerator
from test_case_creation.feature_management.feature_processor import FeatureProcessor
from test_case_creation.test_case_handling.test_case_analyzer import analyze_test_cases_with_embeddings
from test_case_creation.helpers.json_parser import format_steps
from test_case_creation.helpers.common_utils import print_progress, print_success, print_warning, print_error
from test_case_creation.data_services.embeddings import EmbeddingsGenerator
from test_case_creation.config.config import TestCaseAgent, TestCaseCritic, TestCaseOptimizer
from test_case_creation.test_case_handling.test_case_workflow import process_and_store_test_cases
from test_case_creation.test_case_handling.criteria_removal_handler import mark_deprecated_criteria_in_test_cases_with_critique
from test_case_creation.data_services.criteria_mapper import map_test_cases_to_feature_criteria
import time
   

# Helper functions for message formatting (reusing from test_case_workflow.py)
def print_progress(message): print(f"🔹 {message}")
def print_success(message): print(f"✅ {message}")
def print_warning(message): print(f"⚠️ {message}")
def print_error(message): print(f"❌ {message}")


async def analyze_criteria_changes(original_criteria, new_criteria_list):
    """
    Analyze changes between original and new acceptance criteria.
    Modified to always treat new criteria as added, never as reactivated.
    
    Args:
        original_criteria (list): List of original criteria objects with id and description
        new_criteria_list (list): List of new criteria descriptions (strings)
        
    Returns:
        dict: Dictionary categorizing criteria changes
    """
    result = {
        "unchanged": [],
        "modified": [],
        "added": [],
        "removed": [],
        # Note: "reactivated" category removed
    }
    
    # Debug output
    print(f"🔹 Original criteria count: {len(original_criteria)}")
    print(f"🔹 New criteria count: {len(new_criteria_list)}")
    
    # We only care about active criteria now
    active_criteria = [c for c in original_criteria if c.get("status", "Active") == "Active"]
    
    print(f"🔹 Active criteria: {len(active_criteria)}")
    # Removed the debugging for deprecated criteria
    
    # Convert lists to lowercase for easier comparison
    active_desc_list = [c.get("description", "").lower().strip() for c in active_criteria]
    new_desc_list = [desc.lower().strip() for desc in new_criteria_list]
    
    # Step 1: Find unchanged active criteria
    matched_active_indices = set()
    matched_new_indices = set()
    
    for i, original in enumerate(active_criteria):
        original_desc_lower = active_desc_list[i]
        
        for j, new_desc_lower in enumerate(new_desc_list):
            if original_desc_lower == new_desc_lower and j not in matched_new_indices:
                result["unchanged"].append(original)
                matched_active_indices.add(i)
                matched_new_indices.add(j)
                break
    
    # Step 2: Skip reactivation detection completely
    # The old reactivation code has been removed
    
    # Step 3: Use LLM to compare remaining criteria for semantic differences
    for i, original in enumerate(active_criteria):
        if i in matched_active_indices:
            continue
            
        original_desc = original.get("description", "")
        
        best_match_idx = -1
        best_match_score = 0.7  # Minimum similarity threshold
        
        for j, new_desc_lower in enumerate(new_desc_list):
            if j in matched_new_indices:
                continue
                
            # First use simple similarity to filter obvious non-matches
            score = calculate_text_similarity(active_desc_list[i], new_desc_lower)
            
            if score > 0.5:  # If there's basic similarity, check semantic meaning with LLM
                # Use LLM to compare the criteria semantically
                comparison = await compare_criteria_with_llm(original_desc, new_criteria_list[j])
                
                if comparison["is_same_meaning"]:
                    # They have the same meaning according to LLM, mark as unchanged
                    result["unchanged"].append(original)
                    matched_active_indices.add(i)
                    matched_new_indices.add(j)
                    print(f"🔹 LLM found semantically equivalent criteria: {original.get('id')}")
                    break
                else:
                    # They are different but related, mark as modified
                    result["modified"].append((original, new_criteria_list[j]))
                    matched_active_indices.add(i)
                    matched_new_indices.add(j)
                    print(f"🔹 LLM detected modified criteria: {original.get('id')}")
                    print(f"   - Significance: {comparison['significance']}")
                    break
            
            # If we haven't found a semantic match but there's high lexical similarity
            elif score > best_match_score:
                best_match_score = score
                best_match_idx = j
        
        # If no semantic match found but we have a good lexical match
        if i not in matched_active_indices and best_match_idx >= 0:
            result["modified"].append((original, new_criteria_list[best_match_idx]))
            matched_active_indices.add(i)
            matched_new_indices.add(best_match_idx)
    
    # Step 4: Explicitly check for removed criteria (only from active criteria)
    for i, original in enumerate(active_criteria):
        if i not in matched_active_indices:
            result["removed"].append(original)
            print(f"🔹 Detected removed criteria: {original.get('description', '')[:50]}...")
    
    # Step 5: Add remaining new criteria as added
    for j, new_desc in enumerate(new_criteria_list):
        if j not in matched_new_indices:
            result["added"].append(new_desc)
            print(f"🔹 Detected added criteria: {new_desc[:50]}...")
    
    # Print summary - updated to remove reference to reactivated
    print(f"🔹 Changes detected: {len(result['unchanged'])} unchanged, {len(result['modified'])} modified, " +
          f"{len(result['added'])} added, {len(result['removed'])} removed")
    
    return result

# Enhanced update_feature_workflow function for updating feature and managing test case status

async def update_feature_workflow(feature_data):
    """
    Enhanced workflow for updating an existing feature.
    Now acts as a router to specialized handlers based on update type.
    
    Args:
        feature_data (dict): The processed feature data with the update
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not feature_data or not feature_data.get('id'):
        print_error(f"Invalid feature data for update")
        return False
    
    print_progress(f"Starting enhanced update workflow for feature: {feature_data['id']}")
    feature_id = feature_data['id']
    
    try:
        # Get original feature data
        original_feature = await get_original_feature(feature_id)
        if not original_feature:
            print_warning(f"Couldn't find original feature with ID {feature_id}. Will proceed as new feature.")
            return False
        
        # Determine update type
        update_type, criteria_changes = await handle_determine_update_type(feature_data, original_feature)
        
        # Route to the appropriate handler based on update type
        if update_type == "NO_CHANGES":
            print_success(f"No changes detected in criteria. Skipping ALL database operations.")
            print_success("Feature update workflow completed successfully (no changes needed)")
            return True
        elif update_type == "MODIFIED":
            return await handle_update_with_modified_criteria_flow(feature_data, original_feature, criteria_changes)
        elif update_type == "ADDED":
            return await handle_update_with_added_criteria_flow(feature_data, original_feature, criteria_changes)
        elif update_type == "REMOVED":
            return await handle_update_with_removed_criteria_flow(feature_data, original_feature, criteria_changes)
        elif update_type == "COMBINED":
            return await handle_combined_update_flow(feature_data, original_feature, criteria_changes)
        else:
            print_error(f"Unknown update type: {update_type}")
            return False
            
    except Exception as e:
        print_error(f"Error in update feature workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
                    
async def get_original_feature(feature_id):
    """
    Retrieve the original feature data from Azure Cognitive Search.
    
    Args:
        feature_id (str): The feature ID to retrieve
        
    Returns:
        dict: The original feature data or None if not found
    """
    try:
        feature_processor = FeatureProcessor()
        
        # Search for the feature by ID
        results = list(feature_processor.search_client.search(
            search_text="",
            filter=f"id eq '{feature_id}'",
            select=["*"]  # Select all fields
        ))
        
        if results:
            return dict(results[0])  # Convert to dict to make it easier to work with
        else:
            print_warning(f"Feature with ID {feature_id} not found in search index")
            return None
            
    except Exception as e:
        print_error(f"Error retrieving original feature: {str(e)}")
        return None

def calculate_text_similarity(text1, text2):
    """
    Calculate similarity between two texts using token-based approach.
    
    Args:
        text1 (str): First text
        text2 (str): Second text
        
    Returns:
        float: Similarity score between 0 and 1
    """
    # Simple implementation using token overlap
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())
    
    # Remove common stop words
    stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'to', 'of', 'for', 'in', 'with'}
    tokens1 = tokens1.difference(stop_words)
    tokens2 = tokens2.difference(stop_words)
    
    if not tokens1 or not tokens2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    
    if union == 0:
        return 0.0
        
    return intersection / union

def analyze_test_cases(test_cases, criteria_changes):
    """
    Analyze existing test cases and decide which to keep, update, or regenerate.
    Enhanced to handle criteria removal and test case status management.
    
    Args:
        test_cases (list): List of existing test cases
        criteria_changes (dict): The criteria change analysis result
        
    Returns:
        dict: Decision for each test case:
            - keep_unchanged: test cases with only unchanged criteria
            - keep_with_updates: test cases to keep but update criteria mappings
            - regenerate: test cases to regenerate
    """
    result = {
        "keep_unchanged": [],  # Test cases with only unchanged criteria
        "keep_with_updates": [],  # Test cases with some modified criteria
        "regenerate": []  # Test cases with removed criteria or significant changes
    }
    
    # Create sets of criteria IDs for easy lookup
    unchanged_ids = {c.get("id") for c in criteria_changes["unchanged"]}
    modified_ids = {c.get("id") for c, _ in criteria_changes["modified"]}
    removed_ids = {c.get("id") for c in criteria_changes["removed"]}
    
    for test_case in test_cases:
        # Skip already inactive test cases
        if test_case.get("status") == "Inactive":
            continue
            
        # Get criteria metadata for this test case
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        if not criteria_metadata:
            # If no criteria metadata, it's safer to regenerate
            result["regenerate"].append(test_case)
            continue
            
        # Get criteria IDs for this test case
        test_case_criteria_ids = {c.get("criteriaId") for c in criteria_metadata}
        
        # Check for intersection with different categories
        has_unchanged = bool(test_case_criteria_ids.intersection(unchanged_ids))
        has_modified = bool(test_case_criteria_ids.intersection(modified_ids))
        has_removed = bool(test_case_criteria_ids.intersection(removed_ids))
        
        # Count how many criteria of each type
        unchanged_count = len(test_case_criteria_ids.intersection(unchanged_ids))
        modified_count = len(test_case_criteria_ids.intersection(modified_ids))
        removed_count = len(test_case_criteria_ids.intersection(removed_ids))
        total_count = len(test_case_criteria_ids)
        
        # Decision logic
        if has_removed:
            # If ALL criteria are removed, regenerate the test case
            if removed_count == total_count:
                result["regenerate"].append(test_case)
            # If MAJORITY of criteria are removed, regenerate
            elif removed_count > (total_count / 2):
                result["regenerate"].append(test_case)
            # If some criteria removed but still has valid criteria, update it
            elif has_unchanged or has_modified:
                result["keep_with_updates"].append(test_case)
            else:
                # Otherwise regenerate
                result["regenerate"].append(test_case)
        elif has_modified and not has_unchanged:
            # If only verifies modified criteria, likely needs regeneration
            result["regenerate"].append(test_case)
        elif has_modified:
            # If verifies both modified and unchanged criteria, update mappings
            result["keep_with_updates"].append(test_case)
        else:
            # If only verifies unchanged criteria, keep as is
            result["keep_unchanged"].append(test_case)
    
    # Print detailed analysis
    print_progress(f"Test case analysis details:")
    print_progress(f"  - Total test cases analyzed: {len(test_cases)}")
    print_progress(f"  - Keep unchanged: {len(result['keep_unchanged'])}")
    print_progress(f"  - Keep with updates: {len(result['keep_with_updates'])}")
    print_progress(f"  - Regenerate: {len(result['regenerate'])}")
    
    return result

def create_updated_criteria_objects(original_criteria, criteria_changes):
    updated_criteria = []
    
    # 1. Add unchanged criteria as they are
    updated_criteria.extend(criteria_changes["unchanged"])
    print(f"🔹 Added {len(criteria_changes['unchanged'])} unchanged criteria")
    
    # 2. Add modified criteria with updated descriptions but preserved IDs
    for original, new_description in criteria_changes["modified"]:
        # Create a copy with ONLY the fields in the feature schema
        updated = {
            "id": original.get("id", ""),
            "description": new_description,
            "status": "Active",
            "addedDate": datetime.now(timezone.utc).isoformat()
        }
        updated_criteria.append(updated)
    print(f"🔹 Added {len(criteria_changes['modified'])} modified criteria")
    
    # 3. Removed the reactivated criteria handling code
    
    # 4. Add new criteria with new IDs
    next_id = 1
    # Find the highest existing ID number from ALL criteria (active or not)
    for criteria in original_criteria:
        criteria_id = criteria.get("id", "")
        if criteria_id.startswith("AC-"):
            try:
                id_num = int(criteria_id[3:])
                next_id = max(next_id, id_num + 1)
            except ValueError:
                pass
    
    # Add new criteria with new IDs
    for new_description in criteria_changes["added"]:
        criteria_id = f"AC-{next_id:03d}"
        next_id += 1
        
        updated_criteria.append({
            "id": criteria_id,
            "description": new_description,
            "status": "Active",
            "addedDate": datetime.now(timezone.utc).isoformat()
        })
    print(f"🔹 Added {len(criteria_changes['added'])} new criteria")
    
    print(f"🔹 Total updated criteria: {len(updated_criteria)}")
    return updated_criteria

def get_criteria_id_map(criteria_objects):
    """
    Create a mapping of criteria descriptions to their IDs.
    
    Args:
        criteria_objects (list): List of criteria objects
        
    Returns:
        dict: Mapping of lowercase descriptions to criteria objects
    """
    criteria_map = {}
    
    for criteria in criteria_objects:
        if criteria.get("status", "Active") == "Active":  # Only map active criteria
            criteria_id = criteria.get("id")
            criteria_map[criteria_id] = criteria
    
    return criteria_map

async def update_test_case_criteria_mappings(test_cases, criteria_map, feature_id):
    """
    Update criteria mappings for test cases that need updates.
    Enhanced to ensure featureMetadata is preserved.
    
    Args:
        test_cases (list): Test cases to update
        criteria_map (dict): Mapping of criteria descriptions to objects
        feature_id (str): The feature ID to associate with test cases
        
    Returns:
        bool: True if successful, False otherwise
    """
    embeddings_generator = EmbeddingsGenerator()
    update_count = 0
    
    for test_case in test_cases:
        # Get current criteria metadata
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        updated_metadata = []
        
        for criteria in criteria_metadata:
            criteria_id = criteria.get("criteriaId")
            description = criteria.get("description", "").lower().strip()
            
            # Try to find matching criteria in the map
            if criteria_id in criteria_map:
                # Preserve status if it's "Inactive"
                current_status = criteria.get("status")
                updated_metadata.append({
                    "criteriaId": criteria_map[criteria_id]["id"],
                    "description": criteria_map[criteria_id]["description"],
                    "status": "Inactive" if current_status == "Inactive" else criteria_map[criteria_id].get("status", "Active")
                })
            else:
                # Try fuzzy matching if exact match fails
                best_match = None
                best_score = 0.7  # Minimum similarity threshold
                
                for desc, crit in criteria_map.items():
                    score = calculate_text_similarity(description, desc)
                    if score > best_score:
                        best_score = score
                        best_match = crit
                
                if best_match:
                    updated_metadata.append({
                        "criteriaId": best_match["id"],
                        "description": best_match["description"],
                        "status": criteria.get("status", "Active")  # Preserve existing status
                    })
                else:
                    # If no good match, keep the original but mark it
                    print_warning(f"No match found for criteria: {description}")
                    updated_metadata.append(criteria)
        
        # Update the test case if metadata changed or featureMetadata is missing
        needs_update = (updated_metadata != criteria_metadata) or (test_case.get("featureMetadata") is None)

        if needs_update:
            # Fetch the latest version from the database first
            try:
                latest_results = list(embeddings_generator.search_client.search(
                    search_text="",
                    filter=f"id eq '{test_case.get('id')}'",
                    select=["*"]
                ))
                
                if latest_results:
                    # Start with the latest version from the database
                    updated_test_case = dict(latest_results[0])
                    print(f"🔹 Fetched latest version of test case {test_case.get('id')} from database")
                else:
                    # Fall back to original if fetch fails
                    updated_test_case = dict(test_case)
                    print(f"⚠️ Could not fetch latest version of test case {test_case.get('id')}")
            except Exception as e:
                # Log the error and use the original test case
                print(f"⚠️ Error fetching latest test case: {str(e)}")
                updated_test_case = dict(test_case)
            
            # Update criteria metadata if changed
            if updated_metadata != criteria_metadata:
                updated_test_case["criteriaMetadata"] = updated_metadata
            
            # Always ensure proper featureMetadata is set
            updated_test_case["featureMetadata"] = {
                "featureId": feature_id,
                "lastUpdated": datetime.now(timezone.utc).isoformat()
            }
            
            success = embeddings_generator.upload_test_case(updated_test_case)
            if success:
                update_count += 1
                print(f"✅ Updated test case {test_case.get('id')} with proper metadata")
            else:
                print_warning(f"Failed to update test case {test_case.get('id')}")
    
    print_success(f"Updated criteria mappings for {update_count} test cases")
    return True

async def generate_requirement_text(feature_data, added_criteria, modified_criteria_pairs):
    """
    Generate requirements text focused on new and modified criteria.
    
    Args:
        feature_data (dict): Feature data
        added_criteria (list): List of new criteria descriptions
        modified_criteria_pairs (list): List of (original, new) criteria pairs
        
    Returns:
        str: Requirements text for test case generation
    """
    # Get modified criteria descriptions (only the new versions)
    modified_criteria = [new for _, new in modified_criteria_pairs]
    
    # Combine added and modified criteria
    focus_criteria = added_criteria + modified_criteria
    
    # Read the generator prompt template
    PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")
    prompt_file = os.path.join(PROMPTS_DIR, "generator_prompt.txt")
    
    with open(prompt_file, "r", encoding="utf-8") as f:
        template = f.read()
    
    # Create a prefix for test case IDs based on feature title
    prefix = "ENV"  # Default
    title = feature_data.get("title", "") or feature_data.get("name", "")
    if title:
        words = re.findall(r'[A-Z][a-z]*', title.replace(" ", ""))
        if words:
            prefix = "".join(word[0] for word in words).upper()
            # Ensure prefix is at least 3 chars
            if len(prefix) < 3:
                prefix = prefix.ljust(3, 'X')
    
    # Format the template
    description = feature_data.get("description", "")
    criteria_text = "\n".join([f"- {c}" for c in focus_criteria])
    
    # Add focus instruction
    if added_criteria and modified_criteria:
        focus_note = "\nPlease focus on generating test cases for the new and modified criteria listed above. These are recent changes to the feature."
        criteria_text += focus_note
    
    requirement_text = template.replace("{description}", description)
    requirement_text = requirement_text.replace("{criteria}", criteria_text)
    requirement_text = requirement_text.replace("{prefix}", prefix)
    
    return requirement_text

async def generate_selective_test_cases(requirement_text, context_test_cases, criteria_changes):
    """
    Generate test cases for new and modified criteria.
    
    Args:
        requirement_text (str): Requirements text focused on new/modified criteria
        context_test_cases (list): Existing test cases to use as context
        criteria_changes (dict): The criteria change analysis
        
    Returns:
        str: Generated test cases content
    """
    
    # Prepare context with existing test cases
    context = ""
    if context_test_cases:
        context = "\n\nREFERENCE TEST CASES:\n"
        for i, case in enumerate(context_test_cases[:3]):  # Limit to 3 for context
            context += f"\nREFERENCE TEST CASE {i+1}:\n"
            context += f"ID: {case.get('id', 'Unknown')}\n"
            context += f"Title: {case.get('title', 'Unknown')}\n"
            context += f"Steps:\n{case.get('steps', 'None')}\n"
            context += f"Expected Results:\n{case.get('expectedResults', 'None')}\n"
    
    # Add focus instruction based on criteria changes
    focus_instruction = "\n\nPlease generate NEW test cases specifically for:"
    
    if criteria_changes["added"]:
        focus_instruction += "\n- New criteria: " + ", ".join([c[:50] + "..." for c in criteria_changes["added"]])
    
    if criteria_changes["modified"]:
        modified_desc = [new[:50] + "..." for _, new in criteria_changes["modified"]]
        focus_instruction += "\n- Modified criteria: " + ", ".join(modified_desc)
    
    enhanced_prompt = requirement_text + context + focus_instruction
    
    # Generate test cases
    print_progress("Generating test cases for modified/new criteria...")
    test_cases = await generate_test_cases(context_test_cases)
    
    return test_cases

async def process_and_store_selective_test_cases(test_cases_content, feature_data, criteria_objects):
    """
    Process and store selectively generated test cases.
    Maps test cases to the appropriate criteria.
    
    Args:
        test_cases_content (str): Generated test cases content
        feature_data (dict): Feature data
        criteria_objects (list): Updated criteria objects
        
    Returns:
        bool: True if successful, False otherwise
    """
    
    
    # Process the test cases using the existing function
    success = await process_and_store_test_cases(test_cases_content, feature_data)
    
    return success

async def mark_test_cases_inactive(feature_id, test_case_ids, reason="Feature update"):
    """
    Mark specific test cases as inactive.
    Used when test cases are no longer valid due to feature changes.
    
    Args:
        feature_id (str): The feature ID
        test_case_ids (list): List of test case IDs to mark as inactive
        reason (str): Reason for marking the test case as inactive
        
    Returns:
        int: Number of test cases updated
    """
    if not test_case_ids:
        print_progress("No test cases to mark as inactive")
        return 0
        
    print_progress(f"Marking {len(test_case_ids)} test cases as inactive")
    
    # Initialize embeddings generator
    embeddings_generator = EmbeddingsGenerator()
    updated_count = 0
    
    for test_case_id in test_case_ids:
        # Search for the test case
        try:
            results = list(embeddings_generator.search_client.search(
                search_text="",
                filter=f"id eq '{test_case_id}'",
                select=["*"]
            ))
            
            if not results:
                print_warning(f"Test case {test_case_id} not found")
                continue
                
            test_case = dict(results[0])
            
            # Update the test case status
            test_case["status"] = "Inactive"
            # test_case["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            # test_case["statusReason"] = reason
            if "featureMetadata" in test_case:
                test_case["featureMetadata"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            
            # Upload the updated test case
            success = embeddings_generator.upload_test_case(test_case)
            
            if success:
                updated_count += 1
                print_success(f"Successfully marked test case {test_case_id} as inactive")
            else:
                print_warning(f"Failed to update test case {test_case_id}")
                
        except Exception as e:
            print_error(f"Error updating test case {test_case_id}: {str(e)}")
    
    print_success(f"Marked {updated_count} test cases as inactive")
    return updated_count

async def mark_deprecated_criteria_in_test_cases(feature_id, removed_criteria_ids, keep_test_cases=[]):
    """
    Explicitly mark deprecated criteria as inactive in test cases.
    Enhanced to ensure all test cases are properly updated.
    
    Args:
        feature_id (str): The feature ID
        removed_criteria_ids (list): List of criteria IDs that were removed
        keep_test_cases (list): Optional list of test cases to process
        
    Returns:
        int: Number of test cases updated
    """
    if not removed_criteria_ids:
        print(f"🔹 No criteria were removed, no cleanup needed")
        return 0
        
    print(f"🔹 Marking {len(removed_criteria_ids)} removed criteria as inactive in test cases")
    print(f"🔹 Criteria IDs to mark inactive: {', '.join(removed_criteria_ids)}")
    
    # Initialize vector system and embeddings generator
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    # Get test cases to process
    test_cases = keep_test_cases
    if not test_cases:
        test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    
    print(f"🔹 Retrieved {len(test_cases)} test cases to process")
    updated_count = 0
    
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        if not test_case_id:
            continue
            
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        if not criteria_metadata:
            continue
            
        # Debug output
        print(f"🔹 Processing test case {test_case_id} with {len(criteria_metadata)} criteria references")
        
        # Create a deep copy of test case to avoid reference issues
        updated_test_case = dict(test_case)
        new_criteria_metadata = []
        updated = False
        
        # Check each criteria
        for criteria in criteria_metadata:
            criteria_id = criteria.get("criteriaId")
            if not criteria_id:
                continue
                
            # Make a deep copy of the criteria
            new_criteria = dict(criteria)
            
            # If this is a criteria that was removed, mark it as inactive
            if criteria_id in removed_criteria_ids:
                current_status = criteria.get("status")
                
                # Only update if not already inactive
                if current_status != "Inactive":
                    new_criteria["status"] = "Inactive"
                    new_criteria["removedDate"] = datetime.now(timezone.utc).isoformat()
                    updated = True
                    print(f"🔹 Marked criteria {criteria_id} as inactive in test case {test_case_id}")
            
            # Always ensure status is set (not null)
            elif new_criteria.get("status") is None:
                new_criteria["status"] = "Active"
                updated = True
                print(f"🔹 Fixed null status for criteria {criteria_id} in test case {test_case_id}")
                
            new_criteria_metadata.append(new_criteria)
        
        # If anything was updated, update the test case
        if updated:
            updated_test_case["criteriaMetadata"] = new_criteria_metadata
            
            # Ensure featureMetadata is properly set
            if not updated_test_case.get("featureMetadata") or updated_test_case.get("featureMetadata") is None:
                updated_test_case["featureMetadata"] = {
                    "featureId": feature_id,
                    "lastUpdated": datetime.now(timezone.utc).isoformat()
                }
            elif "featureMetadata" in updated_test_case:
                updated_test_case["featureMetadata"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            
            # Upload the updated test case
            try:
                success = embeddings_generator.upload_test_case(updated_test_case)
                if success:
                    updated_count += 1
                    print(f"✅ Successfully updated test case {test_case_id}")
                else:
                    print(f"⚠️ Failed to update test case {test_case_id}")
            except Exception as e:
                print(f"❌ Error updating test case {test_case_id}: {str(e)}")
    
    # If no test cases were updated but there should have been updates, check all test cases
    if updated_count == 0 and len(removed_criteria_ids) > 0:
        print(f"⚠️ No test cases were updated. Attempting more aggressive search...")
        
        # Try to find ALL test cases that might reference these criteria
        all_test_cases = []
        
        for criteria_id in removed_criteria_ids:
            try:
                # Search for test cases with this criteria ID
                criteria_filter = f"criteriaMetadata/any(c: c/criteriaId eq '{criteria_id}')"
                matching_cases = list(embeddings_generator.search_client.search(
                    search_text="*",
                    filter=criteria_filter,
                    select=["*"],
                    top=1000
                ))
                
                if matching_cases:
                    print(f"🔹 Found {len(matching_cases)} test cases with criteria {criteria_id}")
                    all_test_cases.extend(matching_cases)
            except Exception as e:
                print(f"⚠️ Error searching for test cases with criteria {criteria_id}: {str(e)}")
        
        # Process all found test cases directly (without recursion)
        if all_test_cases:
            # Remove duplicates
            unique_ids = set()
            unique_cases = []
            
            for tc in all_test_cases:
                tc_id = tc.get("id")
                if tc_id and tc_id not in unique_ids:
                    unique_ids.add(tc_id)
                    unique_cases.append(tc)
            
            # Process the unique test cases directly in this function
            print(f"🔹 Found {len(unique_cases)} unique test cases with the removed criteria")
            
            # Process each test case without recursion
            fallback_count = 0
            for test_case in unique_cases:
                test_case_id = test_case.get("id")
                if not test_case_id:
                    continue
                    
                criteria_metadata = test_case.get("criteriaMetadata", []) or []
                
                if not criteria_metadata:
                    continue
                    
                # Same logic as above for processing criteria
                updated_test_case = dict(test_case)
                new_criteria_metadata = []
                updated = False
                
                for criteria in criteria_metadata:
                    criteria_id = criteria.get("criteriaId")
                    if not criteria_id:
                        continue
                        
                    new_criteria = dict(criteria)
                    
                    if criteria_id in removed_criteria_ids:
                        current_status = criteria.get("status")
                        
                        if current_status != "Inactive":
                            new_criteria["status"] = "Inactive"
                            new_criteria["removedDate"] = datetime.now(timezone.utc).isoformat()
                            updated = True
                            print(f"🔹 Marked criteria {criteria_id} as inactive in test case {test_case_id} (fallback)")
                    
                    elif new_criteria.get("status") is None:
                        new_criteria["status"] = "Active"
                        updated = True
                        print(f"🔹 Fixed null status for criteria {criteria_id} in test case {test_case_id} (fallback)")
                        
                    new_criteria_metadata.append(new_criteria)
                
                if updated:
                    updated_test_case["criteriaMetadata"] = new_criteria_metadata
                    
                    # Ensure featureMetadata is set
                    if not updated_test_case.get("featureMetadata") or updated_test_case.get("featureMetadata") is None:
                        updated_test_case["featureMetadata"] = {
                            "featureId": feature_id,
                            "lastUpdated": datetime.now(timezone.utc).isoformat()
                        }
                    elif "featureMetadata" in updated_test_case:
                        updated_test_case["featureMetadata"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
                    
                    try:
                        success = embeddings_generator.upload_test_case(updated_test_case)
                        if success:
                            fallback_count += 1
                            print(f"✅ Successfully updated test case {test_case_id} (fallback)")
                        else:
                            print(f"⚠️ Failed to update test case {test_case_id} (fallback)")
                    except Exception as e:
                        print(f"❌ Error updating test case {test_case_id} (fallback): {str(e)}")
            
            updated_count += fallback_count
            print(f"✅ Marked deprecated criteria as inactive in {fallback_count} additional test cases")

async def reactivate_criteria_in_test_cases(feature_id, reactivated_criteria_ids, new_descriptions=None):
    """
    Reactivate previously inactive criteria references in test cases.
    """
    if not reactivated_criteria_ids:
        print(f"🔹 No criteria were reactivated, no updates needed")
        return 0
        
    print(f"🔹 Reactivating {len(reactivated_criteria_ids)} criteria in test cases")
    print(f"🔹 Criteria IDs to reactivate: {', '.join(reactivated_criteria_ids)}")
    
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    updated_count = 0
    
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        updated = False
        new_metadata = []
        
        for criteria in criteria_metadata:
            criteria_id = criteria.get("criteriaId")
            description = criteria.get("description", "")
            
            if criteria_id in reactivated_criteria_ids:
                if new_descriptions and criteria_id in new_descriptions:
                    description = new_descriptions[criteria_id]
                
                new_metadata.append({
                    "criteriaId": criteria_id,
                    "description": description,
                    "status": "Active"
                    # No removedDate for active criteria
                })
                
                if criteria.get("status") == "Inactive":
                    updated = True
                    print(f"🔹 Reactivated criteria {criteria_id} in test case {test_case_id}")
            else:
                # Copy existing criteria with its current status
                new_criteria = {
                    "criteriaId": criteria_id,
                    "description": description,
                    "status": criteria.get("status", "Active")
                }
                
                # Only include removedDate if status is Inactive
                if criteria.get("status") == "Inactive" and criteria.get("removedDate"):
                    new_criteria["removedDate"] = criteria.get("removedDate")
                
                new_metadata.append(new_criteria)
        
        if updated:
            test_case["criteriaMetadata"] = new_metadata
            
            if "featureMetadata" in test_case:
                test_case["featureMetadata"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            
            success = embeddings_generator.upload_test_case(test_case)
            if success:
                updated_count += 1
                print(f"✅ Successfully updated test case {test_case_id}")
            else:
                print(f"⚠️ Failed to update test case {test_case_id}")
    
    print(f"✅ Reactivated criteria in {updated_count} test cases")
    return updated_count

async def fix_null_status_in_test_cases(feature_id):
    """
    Fix any existing test case criteria with null status.
    
    Args:
        feature_id (str): The feature ID
        
    Returns:
        int: Number of test cases fixed
    """
    print(f"🔹 Checking for test cases with null criteria status...")
    
    # Initialize vector system and embeddings generator
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    # Get all test cases for this feature
    test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    fixed_count = 0
    
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        updated = False
        for criteria in criteria_metadata:
            if criteria.get("status") is None:
                # Set status to Active for criteria with null status
                criteria["status"] = "Active"
                updated = True
                print(f"🔹 Fixed null status for criteria {criteria.get('criteriaId')} in test case {test_case_id}")
        
        if updated:
            # Update the test case
            success = embeddings_generator.upload_test_case(test_case)
            if success:
                fixed_count += 1
                print(f"✅ Successfully fixed test case {test_case_id}")
            else:
                print(f"⚠️ Failed to update test case {test_case_id}")
    
    print(f"✅ Fixed null status in {fixed_count} test cases")
    return fixed_count

async def fix_missing_feature_metadata(feature_id, criteria_ids=None):
    """
    Fix test cases that are missing feature metadata but contain specific criteria.
    Enhanced with additional safeguards to prevent data loss.
    
    Args:
        feature_id (str): The feature ID to associate with test cases
        criteria_ids (list): Optional list of criteria IDs to look for (if None, fixes all test cases)
        
    Returns:
        int: Number of test cases updated
    """
    print(f"🔹 Looking for test cases with missing feature metadata that should be associated with {feature_id}")
    
    # Initialize embeddings generator
    embeddings_generator = EmbeddingsGenerator()
    
    # Search for all test cases
    try:
        # Since we can't filter by featureMetadata (it's null), we search all test cases
        all_results = list(embeddings_generator.search_client.search(
            search_text="*",  # Search all
            filter="",  # No filter
            select=["*"],  # Select ALL fields to ensure we have everything
            top=1000  # Adjust as needed
        ))
        
        print(f"🔹 Found {len(all_results)} total test cases to check")
        
        # Track updated test cases
        updated_count = 0
        
        # Filter test cases that need updating
        for test_case in all_results:
            test_case_id = test_case.get("id")
            criteria_metadata = test_case.get("criteriaMetadata", []) or []
            feature_metadata = test_case.get("featureMetadata")
            
            # Create a complete copy of the test case to avoid reference issues
            updated_test_case = dict(test_case)
            
            # Check if this test case should be updated
            should_update = False
            
            # Check if feature metadata is missing or incorrect
            if feature_metadata is None or not feature_metadata.get("featureId"):
                if criteria_ids:
                    # Only update if it contains any of the specified criteria
                    for criteria in criteria_metadata:
                        if criteria.get("criteriaId") in criteria_ids:
                            should_update = True
                            print(f"🔹 Test case {test_case_id} has criteria {criteria.get('criteriaId')} but missing feature metadata")
                            break
                else:
                    # Update all test cases with missing feature metadata
                    should_update = True
                    print(f"🔹 Test case {test_case_id} has missing feature metadata")
            
            # Update the test case if needed
            if should_update:
                print(f"🔹 Updating test case {test_case_id} with feature metadata for {feature_id}")
                
                # Only modify the featureMetadata field, leave everything else untouched
                updated_test_case["featureMetadata"] = {
                    "featureId": feature_id,
                    "lastUpdated": datetime.now(timezone.utc).isoformat()
                }
                
                # Verify all required fields are present before uploading
                required_fields = ["id", "title", "steps", "expectedResults"]
                missing_fields = [field for field in required_fields if not updated_test_case.get(field)]
                
                if missing_fields:
                    print(f"⚠️ Test case {test_case_id} is missing required fields: {', '.join(missing_fields)}")
                    continue
                
                # Print the test case before uploading (for debugging)
                print(f"🔹 About to update test case {test_case_id} with fields:")
                for key in updated_test_case:
                    if key != "vector":  # Skip the vector field which is large
                        print(f"   - {key}: {type(updated_test_case[key])}")
                
                # Upload the updated test case
                try:
                    success = embeddings_generator.upload_test_case(updated_test_case)
                    
                    if success:
                        updated_count += 1
                        print(f"✅ Successfully updated test case {test_case_id} with feature metadata")
                    else:
                        print(f"⚠️ Failed to update test case {test_case_id}")
                except Exception as e:
                    print(f"❌ Error updating test case {test_case_id}: {str(e)}")
        
        print(f"✅ Updated feature metadata for {updated_count} test cases")
        return updated_count
        
    except Exception as e:
        print(f"❌ Error fixing feature metadata: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0
    
async def fix_test_case_metadata_issues(feature_id, fix_null_status=True):
    """
    Comprehensive fix for test case metadata issues:
    - Fixes missing feature metadata
    - Fixes null status values in criteria
    - Ensures all test cases have proper associations
    
    Args:
        feature_id (str): The feature ID to associate with test cases
        fix_null_status (bool): Whether to also fix null status values
        
    Returns:
        int: Number of test cases fixed
    """
    print(f"🔹 Fixing metadata issues for test cases related to feature {feature_id}")
    
    # Initialize components
    embeddings_generator = EmbeddingsGenerator()
    vector_system = VectorRetrievalSystem()
    
    # First, get all test cases for this feature
    # This will find test cases that already have the correct featureMetadata
    feature_test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    
    # Then, search for all test cases that might be related to this feature
    # This will include test cases with missing featureMetadata
    feature_processor = FeatureProcessor()
    feature_results = list(feature_processor.search_client.search(
        search_text="",
        filter=f"id eq '{feature_id}'",
        select=["acceptanceCriteria"]
    ))
    
    criteria_ids = []
    if feature_results and feature_results[0].get("acceptanceCriteria"):
        criteria_ids = [c.get("id") for c in feature_results[0].get("acceptanceCriteria") if c.get("id")]
    
    # Track test cases by ID to avoid duplicates
    test_case_map = {tc.get("id"): tc for tc in feature_test_cases if tc.get("id")}
    
    # Now search for test cases with any of these criteria
    for criteria_id in criteria_ids:
        try:
            criteria_filter = f"criteriaMetadata/any(c: c/criteriaId eq '{criteria_id}')"
            matching_cases = list(embeddings_generator.search_client.search(
                search_text="*",
                filter=criteria_filter,
                select=["*"],
                top=1000
            ))
            
            # Add to the map, avoiding duplicates
            for tc in matching_cases:
                tc_id = tc.get("id")
                if tc_id and tc_id not in test_case_map:
                    test_case_map[tc_id] = tc
                    
        except Exception as e:
            print(f"⚠️ Error searching for test cases with criteria {criteria_id}: {str(e)}")
    
    # Process all found test cases
    fixed_count = 0
    
    for tc_id, test_case in test_case_map.items():
        updated = False
        updated_test_case = dict(test_case)
        
        # 1. Fix missing feature metadata
        if test_case.get("featureMetadata") is None or not test_case.get("featureMetadata").get("featureId"):
            updated_test_case["featureMetadata"] = {
                "featureId": feature_id,
                "lastUpdated": datetime.now(timezone.utc).isoformat()
            }
            updated = True
            print(f"🔹 Setting missing feature metadata for test case {tc_id}")
        
        # 2. Fix null status values in criteria
        if fix_null_status:
            criteria_metadata = test_case.get("criteriaMetadata", []) or []
            updated_criteria = []
            criteria_updated = False
            
            for criteria in criteria_metadata:
                updated_criteria_item = dict(criteria)
                
                # Fix null status
                if criteria.get("status") is None:
                    updated_criteria_item["status"] = "Active"
                    criteria_updated = True
                    print(f"🔹 Fixed null status for criteria {criteria.get('criteriaId')} in test case {tc_id}")
                
                updated_criteria.append(updated_criteria_item)
            
            if criteria_updated:
                updated_test_case["criteriaMetadata"] = updated_criteria
                updated = True
        
        # Update the test case if needed
        if updated:
            # Ensure required fields are present
            if not updated_test_case.get("title") or not updated_test_case.get("steps") or not updated_test_case.get("expectedResults"):
                print(f"⚠️ Test case {tc_id} is missing required fields, skipping update")
                continue
                
            try:
                success = embeddings_generator.upload_test_case(updated_test_case)
                if success:
                    fixed_count += 1
                    print(f"✅ Fixed metadata for test case {tc_id}")
                else:
                    print(f"⚠️ Failed to update test case {tc_id}")
            except Exception as e:
                print(f"❌ Error updating test case {tc_id}: {str(e)}")
    
    print(f"✅ Fixed metadata issues in {fixed_count} test cases for feature {feature_id}")
    return fixed_count

async def verify_criteria_status_consistency(feature_id):
    """
    Verify and fix status consistency between feature criteria and test case criteria.
    Should be run after feature updates to ensure all test cases reflect proper criteria status.
    
    Args:
        feature_id (str): The feature ID to verify
        
    Returns:
        int: Number of test cases fixed
    """
    print(f"🔹 Verifying criteria status consistency for feature {feature_id}")
    
    # Get feature data to get current criteria status
    feature_processor = FeatureProcessor()
    feature_results = list(feature_processor.search_client.search(
        search_text="",
        filter=f"id eq '{feature_id}'",
        select=["acceptanceCriteria"]
    ))
    
    if not feature_results:
        print(f"⚠️ Cannot find feature {feature_id}")
        return 0
        
    # Get criteria status from feature
    feature_criteria = {}
    for criteria in feature_results[0].get("acceptanceCriteria", []):
        criteria_id = criteria.get("id")
        if criteria_id:
            feature_criteria[criteria_id] = {
                "status": criteria.get("status", "Active"),
                "description": criteria.get("description", "")
            }
    
    print(f"🔹 Found {len(feature_criteria)} criteria in feature {feature_id}")
    
    # Get all test cases for this feature
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    
    print(f"🔹 Retrieved {len(test_cases)} test cases to check")
    fixed_count = 0
    
    # Check each test case
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        if not criteria_metadata:
            continue
            
        # Check for inconsistencies
        updated_test_case = dict(test_case)
        new_criteria_metadata = []
        updated = False
        
        for criteria in criteria_metadata:
            criteria_id = criteria.get("criteriaId")
            if not criteria_id:
                continue
                
            # Make a copy of the criteria
            new_criteria = dict(criteria)
            
            # Check if this criteria exists in the feature
            if criteria_id in feature_criteria:
                feature_status = feature_criteria[criteria_id]["status"]
                test_case_status = criteria.get("status")
                
                # Fix null status
                if test_case_status is None:
                    new_criteria["status"] = feature_status
                    updated = True
                    print(f"🔹 Fixed null status for criteria {criteria_id} in test case {test_case_id}")
                
                # Fix inconsistent status
                elif test_case_status != feature_status:
                    if feature_status == "Deprecated" and test_case_status != "Inactive":
                        # If deprecated in feature but not inactive in test case
                        new_criteria["status"] = "Inactive"
                        new_criteria["removedDate"] = datetime.now(timezone.utc).isoformat()
                        updated = True
                        print(f"🔹 Updated criteria {criteria_id} status from {test_case_status} to Inactive in test case {test_case_id}")
                    elif feature_status == "Active" and test_case_status != "Active":
                        # If active in feature but not in test case
                        new_criteria["status"] = "Active"
                        if "removedDate" in new_criteria:
                            del new_criteria["removedDate"]
                        updated = True
                        print(f"🔹 Updated criteria {criteria_id} status from {test_case_status} to Active in test case {test_case_id}")
            else:
                # Criteria not in feature (might be old/removed)
                if criteria.get("status") != "Inactive":
                    new_criteria["status"] = "Inactive"
                    new_criteria["removedDate"] = datetime.now(timezone.utc).isoformat()
                    updated = True
                    print(f"🔹 Marked orphaned criteria {criteria_id} as Inactive in test case {test_case_id}")
            
            new_criteria_metadata.append(new_criteria)
        
        # Update test case if needed
        if updated:
            updated_test_case["criteriaMetadata"] = new_criteria_metadata
            
            # Ensure featureMetadata is set
            if "featureMetadata" in updated_test_case and updated_test_case["featureMetadata"]:
                updated_test_case["featureMetadata"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            else:
                updated_test_case["featureMetadata"] = {
                    "featureId": feature_id,
                    "lastUpdated": datetime.now(timezone.utc).isoformat()
                }
            
            # Upload the updated test case
            success = embeddings_generator.upload_test_case(updated_test_case)
            if success:
                fixed_count += 1
                print(f"✅ Fixed criteria status in test case {test_case_id}")
            else:
                print(f"⚠️ Failed to update test case {test_case_id}")
    
    print(f"✅ Fixed criteria status in {fixed_count} test cases")
    return fixed_count

async def update_test_case_content(test_cases_to_update, changed_criteria):
    """
    Update the content of test cases based on changed criteria.
    Enhanced with critique and optimization loops for better quality.
    
    Args:
        test_cases_to_update (list): Test cases that need content updates
        changed_criteria (list): Criteria that have been modified, with old and new versions
        
    Returns:
        list: Updated test cases with modified content
    """
    
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")
    LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
    OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"🔹 Updating content of {len(test_cases_to_update)} test cases...")
    updated_test_cases = []
    
    # Load the prompt files
    UPDATE_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_update_prompt.txt")
    UPDATE_CRITIC_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_update_critic_prompt.txt")
    UPDATE_OPTIMIZER_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_update_optimizer_prompt.txt")
    ITERATION_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_iteration_prompt.txt")
    
    with open(UPDATE_PROMPT_FILE, "r", encoding="utf-8") as f:
        update_prompt_template = f.read()
    
    with open(UPDATE_CRITIC_PROMPT_FILE, "r", encoding="utf-8") as f:
        update_critic_template = f.read()

    with open(UPDATE_OPTIMIZER_PROMPT_FILE, "r", encoding="utf-8") as f:
        update_optimizer_template = f.read()
        
    with open(ITERATION_PROMPT_FILE, "r", encoding="utf-8") as f:
        iteration_prompt_template = f.read()
    
    # Maximum number of iterations for the critique-update loop
    max_iterations = 2
    
    for test_case in test_cases_to_update:
        test_case_id = test_case.get("id")
        print(f"🔹 Updating content for test case {test_case_id}")
        
        # Get the criteria that affect this test case
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        relevant_changes = []
        
        for criteria_change in changed_criteria:
            old_criteria, new_criteria = criteria_change
            old_id = old_criteria.get("id")
            
            # Check if this test case is mapped to the changed criteria
            for criteria in criteria_metadata:
                if criteria.get("criteriaId") == old_id:
                    relevant_changes.append({
                        "old": old_criteria.get("description"),
                        "new": new_criteria
                    })
        
        if not relevant_changes:
            print(f"⚠️ No relevant criteria changes found for test case {test_case_id}, skipping content update")
            updated_test_cases.append(test_case)
            continue
        
        # Format the changed requirements section
        changed_requirements = ""
        for change in relevant_changes:
            changed_requirements += f"OLD: {change['old']}\n"
            changed_requirements += f"NEW: {change['new']}\n\n"
        
        # Prepare test case in JSON format for processing
        test_case_json = json.dumps({
            "id": test_case.get("id"),
            "title": test_case.get("title"),
            "steps": test_case.get("steps").split("\n") if isinstance(test_case.get("steps"), str) else test_case.get("steps"),
            "expectedResults": test_case.get("expectedResults")
        }, indent=2)
        
        # Initial update generation - use the template
        update_prompt = update_prompt_template.replace("{test_case_id}", test_case.get("id", ""))
        update_prompt = update_prompt.replace("{test_case_title}", test_case.get("title", ""))
        update_prompt = update_prompt.replace("{test_case_steps}", test_case.get("steps", ""))
        update_prompt = update_prompt.replace("{test_case_expected_results}", test_case.get("expectedResults", ""))
        update_prompt = update_prompt.replace("{changed_requirements}", changed_requirements)
        
        # Initial generation
        current_test_case = test_case_json
        
        for iteration in range(1, max_iterations + 1):
            print(f"  🔄 Update iteration {iteration}/{max_iterations}")
            
            # Generate updated test case
            try:
                response = await TestCaseAgent.a_generate_reply(
                    messages=[{"role": "user", "content": update_prompt}]
                )
                
                # Save the response for debugging
                update_response_file = os.path.join(LOGS_DIR, f"update_response_{test_case_id}_iter{iteration}.txt")
                with open(update_response_file, "w", encoding="utf-8") as f:
                    f.write(response)
                
                # Extract JSON from response
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
                if not json_match:
                    json_match = re.search(r'(\{[\s\S]*?\})', response)
                
                if json_match:
                    current_test_case = json_match.group(1)
                else:
                    print(f"⚠️ Could not extract JSON from response for test case {test_case_id}")
                    break
                    
                # If this is the final iteration, skip critique
                if iteration == max_iterations:
                    break
                
                # Add critique step using the template
                critique_prompt = update_critic_template.replace("{current_test_case}", current_test_case)
                critique_prompt = critique_prompt.replace("{changed_requirements}", changed_requirements)
                
                # Get critique
                critique = await TestCaseCritic.a_generate_reply(
                    messages=[{"role": "user", "content": critique_prompt}]
                )
                
                # Save critique for debugging
                critique_file = os.path.join(LOGS_DIR, f"update_critique_{test_case_id}_iter{iteration}.txt")
                with open(critique_file, "w", encoding="utf-8") as f:
                    f.write(critique)
                
                # Update the prompt for next iteration - use the iteration prompt template
                update_prompt = iteration_prompt_template.replace("{current_test_case}", current_test_case)
                update_prompt = update_prompt.replace("{critique}", critique)
                update_prompt = update_prompt.replace("{changed_requirements}", changed_requirements)
                
            except Exception as e:
                print(f"⚠️ Error in update iteration {iteration}: {str(e)}")
                break
        
        # Add optimizer step after the critique-update loops
        try:
            # Create optimizer prompt using template
            optimizer_prompt = update_optimizer_template.replace("{current_test_case}", current_test_case)
            optimizer_prompt = optimizer_prompt.replace("{changed_requirements}", changed_requirements)
            
            # Get optimized version
            optimized_response = await TestCaseOptimizer.a_generate_reply(
                messages=[{"role": "user", "content": optimizer_prompt}]
            )
            
            # Save optimizer response for debugging
            optimizer_file = os.path.join(LOGS_DIR, f"update_optimizer_{test_case_id}.txt")
            with open(optimizer_file, "w", encoding="utf-8") as f:
                f.write(optimized_response)
            
            # Extract JSON from optimized response
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', optimized_response)
            if not json_match:
                json_match = re.search(r'(\{[\s\S]*?\})', optimized_response)
            
            if json_match:
                optimized_test_case = json_match.group(1)
                
                # Extract the optimized test case
                try:
                    updated_tc = json.loads(optimized_test_case)
                except json.JSONDecodeError:
                    print(f"⚠️ Failed to parse optimized JSON for test case {test_case_id}")
                    # Fall back to pre-optimized version
                    try:
                        updated_tc = json.loads(current_test_case)
                    except json.JSONDecodeError:
                        print(f"⚠️ Failed to parse JSON for test case {test_case_id}")
                        updated_test_cases.append(test_case)  # Keep original
                        continue
            else:
                print(f"⚠️ Could not extract JSON from optimizer response for test case {test_case_id}")
                # Fall back to pre-optimized version
                try:
                    updated_tc = json.loads(current_test_case)
                except json.JSONDecodeError:
                    print(f"⚠️ Failed to parse JSON for test case {test_case_id}")
                    updated_test_cases.append(test_case)  # Keep original
                    continue
            
            # Preserve original metadata
            updated_tc["id"] = test_case.get("id")
            updated_tc["createdDate"] = test_case.get("createdDate")
            updated_tc["status"] = test_case.get("status", "Active")
            updated_tc["version"] = test_case.get("version", "1.0")
            updated_tc["featureMetadata"] = test_case.get("featureMetadata")
            updated_tc["criteriaMetadata"] = test_case.get("criteriaMetadata")
            
            # Format all fields that might come as arrays
            updated_tc["steps"] = format_steps(updated_tc.get("steps", ""))
            updated_tc["expectedResults"] = format_steps(updated_tc.get("expectedResults", ""))
            updated_tc["title"] = format_steps(updated_tc.get("title", ""))
            
            # Save updated test case to file
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            updated_tc_file = os.path.join(OUTPUT_DIR, f"UpdatedTestCase_{test_case_id}_{timestamp}.txt")
            
            try:
                with open(updated_tc_file, "w", encoding="utf-8") as f:
                    f.write(f"UPDATED TEST CASE - {datetime.now().isoformat()}\n\n")
                    f.write(f"ID: {updated_tc.get('id')}\n")
                    f.write(f"Title: {updated_tc.get('title')}\n")
                    f.write(f"Steps:\n{updated_tc.get('steps')}\n")
                    f.write(f"Expected Results:\n{updated_tc.get('expectedResults')}\n\n")
                    f.write(f"Status: {updated_tc.get('status')}\n")
                    
                    # Add original test case for comparison
                    f.write("\n\n------- ORIGINAL TEST CASE -------\n\n")
                    f.write(f"Original Title: {test_case.get('title')}\n")
                    f.write(f"Original Steps:\n{test_case.get('steps')}\n")
                    f.write(f"Original Expected Results:\n{test_case.get('expectedResults')}\n")
                
                print(f"✅ Saved updated test case to {updated_tc_file}")
            except Exception as e:
                print(f"⚠️ Error saving updated test case: {str(e)}")
            
            print(f"✅ Successfully updated content for test case {test_case_id}")
            updated_test_cases.append(updated_tc)
            
            # Log the changes
            print(f"  - Old title: {test_case.get('title')}")
            print(f"  - New title: {updated_tc.get('title')}")
            
            # Upload the updated test case
            embeddings_generator = EmbeddingsGenerator()
            success = embeddings_generator.upload_test_case(updated_tc)
            
            if success:
                print(f"✅ Successfully uploaded updated test case {test_case_id}")

                time.sleep(2)
                
                # Verify database update by retrieving the test case
                try:
                    # Check what's actually in the database
                    verify_results = list(embeddings_generator.search_client.search(
                        search_text="",
                        filter=f"id eq '{test_case_id}'",
                        select=["id", "title", "steps", "expectedResults"]
                    ))
                    
                    if verify_results:
                        db_tc = verify_results[0]
                        verify_file = os.path.join(OUTPUT_DIR, f"Verification_{test_case_id}_{timestamp}.txt")
                        
                        with open(verify_file, "w", encoding="utf-8") as f:
                            f.write(f"DATABASE VERIFICATION - {datetime.now().isoformat()}\n\n")
                            f.write(f"ID: {db_tc.get('id')}\n")
                            f.write(f"Title: {db_tc.get('title')}\n")
                            f.write(f"Steps:\n{db_tc.get('steps')}\n")
                            f.write(f"Expected Results:\n{db_tc.get('expectedResults')}\n\n")
                            
                            # Check if update was successful
                            if db_tc.get('title') == updated_tc.get('title'):
                                f.write("\nVERIFICATION: Update successful!\n")
                            else:
                                f.write("\nVERIFICATION FAILED: Database has different content\n")
                                f.write(f"Expected title: {updated_tc.get('title')}\n")
                                f.write(f"Database title: {db_tc.get('title')}\n")
                        
                        print(f"✅ Saved database verification to {verify_file}")
                except Exception as e:
                    print(f"⚠️ Error verifying database update: {str(e)}")
            else:
                print(f"⚠️ Failed to upload updated test case {test_case_id}")
                
        except Exception as e:
            print(f"❌ Error finalizing test case {test_case_id}: {str(e)}")
            updated_test_cases.append(test_case)  # Keep original if update fails
    
    return updated_test_cases

async def compare_criteria_with_llm(original_desc, new_desc):
    """
    Use the LLM to compare two criteria descriptions for semantic differences.
    
    Args:
        original_desc (str): Original criterion description
        new_desc (str): New criterion description
        
    Returns:
        dict: Analysis result with semantic equivalence and change significance
    """
    from config.config import TestCaseAgent
    
    # Load the criteria comparison prompt
    PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")
    COMPARISON_PROMPT_FILE = os.path.join(PROMPTS_DIR, "criteria_comparison_prompt.txt")
    
    with open(COMPARISON_PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt_template = f.read()
    
    # Format the prompt with the criteria
    prompt = prompt_template.replace("{original_criteria}", original_desc)
    prompt = prompt.replace("{new_criteria}", new_desc)
    
    # Get LLM response
    response = await TestCaseAgent.a_generate_reply(
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse the response to extract the analysis
    lines = response.lower().split("\n")
    is_equivalent = False
    
    # Look for yes/no in the first few lines
    for line in lines[:5]:
        if "semantically equivalent" in line or "are they semantically equivalent" in line:
            is_equivalent = "yes" in line.lower() and "no" not in line.lower()
            break
    
    # Default to medium significance if different
    significance = "Medium"
    if not is_equivalent:
        for line in lines:
            if "significance" in line:
                if "high" in line:
                    significance = "High"
                elif "low" in line:
                    significance = "Low"
                break
    
    return {
        "is_same_meaning": is_equivalent,
        "significance": significance,
        "explanation": response
    }

async def handle_modified_criteria(feature_id, modified_criteria, criteria_map):
    """
    Specialized handler for modified criteria.
    Updates test case content and criteria metadata to reflect criteria changes.
    
    Args:
        feature_id (str): The feature ID
        modified_criteria (list): List of (original, new) criteria pairs
        criteria_map (dict): Mapping of criteria IDs to details
        
    Returns:
        bool: True if successful, False otherwise
    """
    print_progress(f"Running specialized handler for {len(modified_criteria)} modified criteria")
    
    # Step 1: Find test cases affected by these modified criteria
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    # Get criteria IDs being modified
    modified_criteria_ids = [original.get('id') for original, _ in modified_criteria]
    print_progress(f"Looking for test cases mapped to criteria: {', '.join(modified_criteria_ids)}")
    
    # Find all test cases for this feature
    all_test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    
    # Filter to only those affected by modified criteria
    affected_test_cases = []
    for test_case in all_test_cases:
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        for criteria in criteria_metadata:
            if criteria.get("criteriaId") in modified_criteria_ids:
                affected_test_cases.append(test_case)
                break
    
    print_progress(f"Found {len(affected_test_cases)} test cases affected by modified criteria")
    
    if not affected_test_cases:
        print_warning("No test cases found that verify the modified criteria")
        return True  # Return success since there's nothing to update
    
    # Step 2: Update the content of affected test cases
    try:
        # Use the existing update_test_case_content function to update the content
        updated_test_cases = await update_test_case_content(
            affected_test_cases, 
            modified_criteria
        )
        
        # Step 3: Update criteria metadata in the test cases
        updated_count = 0
        for updated_tc in updated_test_cases:
            test_case_id = updated_tc.get("id")
            
            # Map of old to new descriptions for quick lookup
            new_descriptions = {}
            for original, new_desc in modified_criteria:
                new_descriptions[original.get("id")] = new_desc
            
            # Update criteria metadata with new descriptions
            updated_criteria_metadata = []
            for criteria_meta in updated_tc.get("criteriaMetadata", []):
                criteria_id = criteria_meta.get("criteriaId")
                
                # Check if this criteria was modified
                if criteria_id in new_descriptions:
                    # Create updated criteria metadata with new description
                    updated_criteria_meta = dict(criteria_meta)  # Make a copy
                    updated_criteria_meta["description"] = new_descriptions[criteria_id]
                    updated_criteria_metadata.append(updated_criteria_meta)
                    print_progress(f"  Updated criteria metadata for {criteria_id} in test case {test_case_id}")
                else:
                    # Keep original criteria metadata
                    updated_criteria_metadata.append(criteria_meta)
            
            # Update the test case with new criteria metadata
            updated_tc["criteriaMetadata"] = updated_criteria_metadata
            
            # Store the updated test case
            success = embeddings_generator.upload_test_case(updated_tc)
            if success:
                updated_count += 1
                print_success(f"Successfully uploaded updated test case {test_case_id} with new content and criteria metadata")
            else:
                print_warning(f"Failed to upload updated test case {test_case_id}")
        
        print_success(f"Updated content and criteria metadata for {updated_count}/{len(affected_test_cases)} test cases")
        return updated_count > 0
        
    except Exception as e:
        print_error(f"Error updating test cases for modified criteria: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
      
async def handle_added_criteria(feature_id, feature_data, added_criteria, updated_criteria_objects):
    """
    Specialized handler for added criteria.
    Generates new test cases for the added criteria.
    
    Args:
        feature_id (str): The feature ID
        feature_data (dict): The feature data
        added_criteria (list): List of new criteria descriptions
        updated_criteria_objects (list): Complete list of criteria objects
        
    Returns:
        bool: True if successful, False otherwise
    """
    print_progress(f"Running specialized handler for {len(added_criteria)} added criteria")
    
    if not added_criteria:
        return True  # Nothing to do
    
    try:
        # Step 1: Generate requirements-specific text for new test cases
        requirement_text = await generate_requirement_text(
            feature_data, added_criteria, []  # No modified criteria to include
        )
        
        # Step 2: Find existing test cases to use as context
        vector_system = VectorRetrievalSystem()
        context_test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
        
        # Step 3: Generate new test cases focused on the added criteria
        print_progress(f"Generating new test cases for {len(added_criteria)} added criteria...")
        
        # Create a criteria changes object with only additions
        focused_criteria_changes = {
            'added': added_criteria,
            'modified': [],
            'removed': [],
            'unchanged': []
        }
        
        new_test_cases_content = await generate_selective_test_cases(
            requirement_text, context_test_cases, focused_criteria_changes
        )
        
        if not new_test_cases_content:
            print_warning("No new test cases were generated for added criteria")
            return False
        
        # Step 4: Process and store the new test cases
        from test_case_creation.helpers.json_parser import parse_test_cases_from_llm_output
        from test_case_creation.data_services.criteria_mapper import map_test_cases_to_feature_criteria
        
        parsed_additional_cases = parse_test_cases_from_llm_output(new_test_cases_content)
        if not parsed_additional_cases:
            print_warning("⚠️ Failed to parse additional test cases")
            return False
            
        print_progress(f"🔹 Found {len(parsed_additional_cases)} additional test cases")
        
        # Step 5: Map the additional test cases to criteria using our feature database function
        # IMPORTANT: This is the key change - use the new mapping function
        print_progress("🔹 Mapping additional test cases to criteria using feature database...")
        try:
            criteria_mapping = await map_test_cases_to_feature_criteria(
                parsed_additional_cases, 
                feature_id  # Pass feature ID to get criteria from database
            )
        except Exception as e:
            print_error(f"Error mapping test cases to criteria: {str(e)}")
            # Fallback mapping if needed
            criteria_mapping = {}
        
        # Step 6: Process and store these test cases
        embeddings_generator = EmbeddingsGenerator()
        additional_test_case_ids = []
        
        # Process each additional test case
        for i, case in enumerate(parsed_additional_cases):
            print_progress(f"Processing additional test case for coverage: {case.get('id')}")
            
            # Add feature metadata
            case["featureMetadata"] = {
                "featureId": feature_id,
                "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            
            # Add criteria metadata from mapping
            if case["id"] in criteria_mapping and criteria_mapping[case["id"]]:
                case["criteriaMetadata"] = criteria_mapping[case["id"]]
                print(f"  Mapped to {len(case['criteriaMetadata'])} acceptance criteria")
            else:
                # Fallback mapping - find active criteria to use
                active_criteria = [c for c in updated_criteria_objects if c.get("status", "Active") == "Active"]
                if active_criteria:
                    first_criteria = active_criteria[0]
                    case["criteriaMetadata"] = [{
                        "criteriaId": first_criteria["id"],
                        "description": first_criteria["description"],
                        "status": "Active"
                    }]
                    print(f"  Mapped to {first_criteria['id']} using fallback")
                else:
                    print_warning(f"No active criteria found for fallback mapping")
                    # Create empty criteria metadata to avoid errors
                    case["criteriaMetadata"] = []
            
            # Upload the test case
            success = embeddings_generator.upload_test_case(case)
            if success:
                additional_test_case_ids.append(case.get("id"))
                print_success(f"✅ Successfully stored additional test case {case.get('id')}")
            else:
                print_warning(f"⚠️ Failed to store additional test case {case.get('id')}")
        
        # Update feature with additional test case IDs
        if additional_test_case_ids:
            feature_processor = FeatureProcessor()
            update_success = feature_processor.update_feature_test_cases(
                feature_id, 
                additional_test_case_ids
            )
            
            if update_success:
                print_success(f"✅ Successfully updated feature {feature_id} with {len(additional_test_case_ids)} new test cases")
            else:
                print_warning(f"⚠️ Failed to update feature {feature_id} with new test cases")
        
        print_success(f"✅ Successfully stored {len(additional_test_case_ids)}/{len(parsed_additional_cases)} additional test cases")
        return True
        
    except Exception as e:
        print_error(f"Error handling added criteria: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
       
async def handle_removed_criteria(feature_id, removed_criteria_ids, criteria_map=None):
    """
    Handle removed criteria by completely removing them from test cases.
    - Delete test cases that have no criteria left after removal
    - For other test cases, completely remove the criteria entries
    
    Args:
        feature_id (str): The feature ID
        removed_criteria_ids (list): List of criteria IDs that were removed
        criteria_map (dict): Optional mapping of criteria IDs (kept for compatibility)
        
    Returns:
        bool: True if successful, False otherwise
    """
    print_progress(f"Running enhanced strict removal handler for {len(removed_criteria_ids)} removed criteria")
    
    if not removed_criteria_ids:
        return True  # Nothing to do
    
    try:
        # Initialize components
        vector_system = VectorRetrievalSystem()
        embeddings_generator = EmbeddingsGenerator()
        
        # Get test cases for this feature
        test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
        print_progress(f"Found {len(test_cases)} test cases to analyze")
        
        # Track test cases to delete and update
        test_cases_to_delete = []
        test_cases_to_update = []
        
        # Analyze each test case
        for test_case in test_cases:
            test_case_id = test_case.get("id")
            
            # Get a deep copy of criteria metadata to ensure we're working with a clean list
            criteria_metadata = test_case.get("criteriaMetadata", []) or []
            if isinstance(criteria_metadata, list):
                criteria_metadata = list(criteria_metadata)  # Create a new list to avoid reference issues
            else:
                criteria_metadata = []  # Fallback if criteriaMetadata isn't a list
                
            print_progress(f"Analyzing test case {test_case_id} with {len(criteria_metadata)} criteria")
            
            # Debug: Print all criteria in this test case
            for c in criteria_metadata:
                print_progress(f"  - Criteria: {c.get('criteriaId')} - {c.get('status')}")
                if c.get('criteriaId') in removed_criteria_ids:
                    print_progress(f"    ⚠️ This criteria should be removed")
            
            # Create a new list WITHOUT the removed criteria
            # Use a more direct filtering approach
            new_criteria_metadata = []
            for criteria in criteria_metadata:
                if criteria.get("criteriaId") not in removed_criteria_ids:
                    new_criteria_metadata.append(criteria)
                else:
                    print_progress(f"  ✅ Excluding criteria {criteria.get('criteriaId')} from updated test case")
            
            # If we removed any criteria
            if len(new_criteria_metadata) != len(criteria_metadata):
                removed_count = len(criteria_metadata) - len(new_criteria_metadata)
                print_progress(f"Removed {removed_count} criteria entries from test case {test_case_id}")
                
                # Debug: Print the new criteria list
                print_progress(f"New criteria list for {test_case_id} contains {len(new_criteria_metadata)} entries:")
                for c in new_criteria_metadata:
                    print_progress(f"  - {c.get('criteriaId')} - {c.get('status')}")
                
                # If no criteria left, delete the test case
                if len(new_criteria_metadata) == 0:
                    test_cases_to_delete.append(test_case_id)
                    print_progress(f"Test case {test_case_id} has no remaining criteria - will be deleted")
                else:
                    # Create a completely new test case object to avoid reference issues
                    updated_test_case = {
                        "id": test_case.get("id"),
                        "title": test_case.get("title"),
                        "steps": test_case.get("steps"),
                        "expectedResults": test_case.get("expectedResults"),
                        "createdDate": test_case.get("createdDate"),
                        "status": test_case.get("status", "Active"),
                        "version": test_case.get("version", "1.0"),
                        # Preserve feature metadata
                        "featureMetadata": test_case.get("featureMetadata"),
                        # Set completely new criteria metadata array
                        "criteriaMetadata": new_criteria_metadata
                    }
                    
                    test_cases_to_update.append(updated_test_case)
                    print_progress(f"Test case {test_case_id} will be updated with {len(new_criteria_metadata)} remaining criteria")
        
        # Delete test cases that have no remaining criteria
        deleted_count = 0
        if test_cases_to_delete:
            print_progress(f"Deleting {len(test_cases_to_delete)} test cases with no remaining criteria")
            
        for test_case in test_cases_to_update:
            try:
                # 1. First, fetch the latest version of the test case
                tc_results = list(embeddings_generator.search_client.search(
                    search_text="",
                    filter=f"id eq '{test_case['id']}'",
                    select=["*"]
                ))
                
                if tc_results:
                    current_tc = dict(tc_results[0])
                    
                    # 2. Create a completely new criteria metadata list WITHOUT the removed criteria
                    new_criteria_metadata = [
                        c for c in current_tc.get("criteriaMetadata", [])
                        if c.get("criteriaId") not in removed_criteria_ids
                    ]
                    
                    # 3. Create a complete new document with ALL fields
                    updated_test_case = {
                        "id": current_tc["id"],
                        "title": current_tc.get("title", ""),
                        "steps": current_tc.get("steps", ""),
                        "expectedResults": current_tc.get("expectedResults", ""),
                        "createdDate": current_tc.get("createdDate", ""),
                        "status": current_tc.get("status", "Active"),
                        "version": current_tc.get("version", "1.0"),
                        "featureMetadata": current_tc.get("featureMetadata", {}),
                        "criteriaMetadata": new_criteria_metadata  # Set completely new list
                    }
                    
                    # 4. Delete the old document first
                    embeddings_generator.search_client.delete_documents(documents=[{"id": current_tc["id"]}])
                    
                    # 5. Wait a bit for deletion to process
                    import time
                    time.sleep(1)
                    
                    # 6. Upload as a completely new document
                    success = embeddings_generator.upload_test_case(updated_test_case)
                    
                    if success:
                        print_success(f"Successfully updated test case {test_case['id']} by delete and recreate")
            except Exception as e:
                print_error(f"Error updating test case: {str(e)}")
        # Update test cases that have remaining criteria
        updated_count = 0
        if test_cases_to_update:
            print_progress(f"Updating {len(test_cases_to_update)} test cases to remove all references to removed criteria")
            
            for updated_test_case in test_cases_to_update:
                try:
                    # First fetch the test case again to ensure we have the latest version
                    tc_results = list(embeddings_generator.search_client.search(
                        search_text="",
                        filter=f"id eq '{updated_test_case['id']}'",
                        select=["*"]
                    ))
                    
                    if tc_results:
                        # Start with the latest version but use our filtered criteria metadata
                        current_tc = dict(tc_results[0])
                        current_tc["criteriaMetadata"] = updated_test_case["criteriaMetadata"]
                        
                        # Recheck that removed criteria IDs are not present
                        current_criteria_ids = [c.get("criteriaId") for c in current_tc.get("criteriaMetadata", [])]
                        for removed_id in removed_criteria_ids:
                            if removed_id in current_criteria_ids:
                                print_error(f"⚠️ CRITICAL: Criteria {removed_id} is still present after preparing update!")
                        
                        # Perform the upload with the properly cleansed document
                        success = embeddings_generator.upload_test_case(current_tc)
                    else:
                        # If we can't fetch the latest version, use our prepared update
                        success = embeddings_generator.upload_test_case(updated_test_case)
                    
                    if success:
                        updated_count += 1
                        print_success(f"Updated test case {updated_test_case.get('id')} - completely removed all references to removed criteria")
                        
                        # Verify the update was successful
                        verification_results = list(embeddings_generator.search_client.search(
                            search_text="",
                            filter=f"id eq '{updated_test_case['id']}'",
                            select=["criteriaMetadata"]
                        ))
                        
                        if verification_results:
                            verification_criteria = verification_results[0].get("criteriaMetadata", [])
                            verification_ids = [c.get("criteriaId") for c in verification_criteria]
                            
                            # Check if any removed criteria are still present
                            remaining_removed = [rid for rid in removed_criteria_ids if rid in verification_ids]
                            
                            if remaining_removed:
                                print_error(f"⚠️ VERIFICATION FAILED: Test case {updated_test_case['id']} still contains removed criteria: {', '.join(remaining_removed)}")
                            else:
                                print_success(f"✅ VERIFICATION PASSED: Test case {updated_test_case['id']} no longer contains any removed criteria")
                    else:
                        print_error(f"Failed to update test case {updated_test_case.get('id')}")
                except Exception as e:
                    print_error(f"Error updating test case {updated_test_case.get('id')}: {str(e)}")
        
        # Print summary
        print_success(f"Processed {len(test_cases)} test cases:")
        print_success(f"  - Deleted: {deleted_count} test cases with no remaining criteria")
        print_success(f"  - Updated: {updated_count} test cases by completely removing all references to removed criteria")
        
        return True
        
    except Exception as e:
        print_error(f"Error handling removed criteria: {str(e)}")
        import traceback
        traceback.print_exc()
        return False         

async def handle_reactivated_criteria(feature_id, reactivated_criteria_ids, criteria_changes):
    """
    Specialized handler for reactivated criteria.
    Reactivates previously inactive criteria in test cases.
    
    Args:
        feature_id (str): The feature ID
        reactivated_criteria_ids (list): List of criteria IDs that were reactivated
        criteria_changes (dict): Complete criteria changes analysis
        
    Returns:
        bool: True if successful, False otherwise
    """
    print_progress(f"Running specialized handler for {len(reactivated_criteria_ids)} reactivated criteria")
    
    if not reactivated_criteria_ids:
        return True  # Nothing to do
    
    try:
        # Create mapping of criteria IDs to new descriptions
        new_descriptions = {}
        for deprecated, new_desc in criteria_changes.get('reactivated', []):
            new_descriptions[deprecated.get('id')] = new_desc
            
        # Reactivate criteria in test cases
        updated_count = await reactivate_criteria_in_test_cases(
            feature_id=feature_id,
            reactivated_criteria_ids=reactivated_criteria_ids,
            new_descriptions=new_descriptions
        )
        
        # Fix test cases that contain criteria from this feature but don't have feature metadata
        await fix_missing_feature_metadata(
            feature_id=feature_id,
            criteria_ids=reactivated_criteria_ids
        )
        
        print_success(f"Reactivated criteria in {updated_count} test cases")
        return True
        
    except Exception as e:
        print_error(f"Error handling reactivated criteria: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def handle_determine_update_type(feature_data, original_feature):
    """
    Determine what kind of update is happening to a feature.
    
    Args:
        feature_data (dict): New feature data from the feature file
        original_feature (dict): Original feature data from the database
        
    Returns:
        str: Update type ('NO_CHANGES', 'ADDED', 'MODIFIED', 'REMOVED', or 'COMBINED')
        dict: Criteria changes analysis
    """
    # Analyze acceptance criteria changes
    criteria_changes = await analyze_criteria_changes(
        original_criteria=original_feature.get('acceptanceCriteria', []),
        new_criteria_list=feature_data.get('acceptance_criteria', [])
    )
    
    # Log the analysis results
    print_progress(f"Acceptance criteria analysis complete:")
    print_progress(f" - Unchanged: {len(criteria_changes['unchanged'])}")
    print_progress(f" - Modified: {len(criteria_changes['modified'])}")
    print_progress(f" - Added: {len(criteria_changes['added'])}")
    print_progress(f" - Removed: {len(criteria_changes['removed'])}")
    
    # Determine update type based on criteria changes
    has_modified = len(criteria_changes['modified']) > 0
    has_added = len(criteria_changes['added']) > 0
    has_removed = len(criteria_changes['removed']) > 0
    
    if not has_modified and not has_added and not has_removed:
        return "NO_CHANGES", criteria_changes
    elif has_modified and not has_added and not has_removed:
        return "MODIFIED", criteria_changes
    elif has_added and not has_modified and not has_removed:
        return "ADDED", criteria_changes
    elif has_removed and not has_modified and not has_added:
        return "REMOVED", criteria_changes
    else:
        return "COMBINED", criteria_changes
    
async def handle_update_with_modified_criteria_flow(feature_data, original_feature, criteria_changes):
    """
    Handle feature update where criteria are modified.
    
    Args:
        feature_data (dict): New feature data
        original_feature (dict): Original feature data
        criteria_changes (dict): Analysis of criteria changes
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    feature_id = feature_data['id']
    print_progress(f"Handling feature update with MODIFIED criteria for feature: {feature_id}")
    
    # Initialize components
    feature_processor = FeatureProcessor()
    
    try:
        # Repair relationships before making changes
        print_progress(f"Repairing feature-test case relationship before update...")
        repair_result = feature_processor.repair_feature_test_case_relationship(feature_id)
        if repair_result["errors"] > 0:
            print_warning(f"Some errors occurred during relationship repair, but continuing with update")
        
        # Create updated acceptance criteria objects
        updated_criteria_objects = create_updated_criteria_objects(
            original_criteria=original_feature.get('acceptanceCriteria', []),
            criteria_changes=criteria_changes
        )
        
        # Update the feature with new criteria
        feature_update_success = feature_processor.update_feature_with_criteria(
            feature_id=feature_id,
            feature_data=feature_data,
            updated_criteria=updated_criteria_objects,
            preserve_test_cases=True
        )

        if not feature_update_success:
            print_error(f"Failed to update feature with modified criteria")
            return False
        
        # Handle modified criteria
        print_progress(f"Processing {len(criteria_changes['modified'])} modified criteria...")
        mod_success = await handle_modified_criteria(
            feature_id=feature_id,
            modified_criteria=criteria_changes['modified'],
            criteria_map=get_criteria_id_map(updated_criteria_objects)
        )
        
        # Verify and fix metadata consistency
        print_progress(f"Verifying criteria status consistency...")
        await verify_criteria_status_consistency(feature_id)
        
        # Final metadata verification
        print_progress(f"Performing final metadata verification...")
        final_fixes = await fix_test_case_metadata_issues(feature_id, fix_null_status=True)
        if final_fixes > 0:
            print_success(f"Fixed metadata issues in {final_fixes} test cases during final verification")
        
        print_success(f"Successfully processed modified criteria for feature: {feature_id}")
        return mod_success
        
    except Exception as e:
        print_error(f"Error handling modified criteria: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
async def handle_update_with_added_criteria_flow(feature_data, original_feature, criteria_changes):
    """
    Handle feature update where new criteria are added.
    
    Args:
        feature_data (dict): New feature data
        original_feature (dict): Original feature data
        criteria_changes (dict): Analysis of criteria changes
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    feature_id = feature_data['id']
    print_progress(f"Handling feature update with ADDED criteria for feature: {feature_id}")
    
    # Initialize components
    feature_processor = FeatureProcessor()
    
    try:
        # Repair relationships before making changes
        print_progress(f"Repairing feature-test case relationship before update...")
        repair_result = feature_processor.repair_feature_test_case_relationship(feature_id)
        if repair_result["errors"] > 0:
            print_warning(f"Some errors occurred during relationship repair, but continuing with update")
        
        # Create updated acceptance criteria objects
        updated_criteria_objects = create_updated_criteria_objects(
            original_criteria=original_feature.get('acceptanceCriteria', []),
            criteria_changes=criteria_changes
        )
        
        # Update the feature with new criteria
        feature_update_success = feature_processor.update_feature_with_criteria(
            feature_id=feature_id,
            feature_data=feature_data,
            updated_criteria=updated_criteria_objects,
            preserve_test_cases=True
        )

        if not feature_update_success:
            print_error(f"Failed to update feature with added criteria")
            return False
        
        # Handle added criteria
        print_progress(f"Processing {len(criteria_changes['added'])} added criteria...")
        add_success = await handle_added_criteria(
            feature_id=feature_id,
            feature_data=feature_data,
            added_criteria=criteria_changes['added'],
            updated_criteria_objects=updated_criteria_objects
        )
        
        # Verify and fix metadata consistency
        print_progress(f"Verifying criteria status consistency...")
        await verify_criteria_status_consistency(feature_id)
        
        # Final metadata verification
        print_progress(f"Performing final metadata verification...")
        final_fixes = await fix_test_case_metadata_issues(feature_id, fix_null_status=True)
        if final_fixes > 0:
            print_success(f"Fixed metadata issues in {final_fixes} test cases during final verification")
        
        print_success(f"Successfully processed added criteria for feature: {feature_id}")
        return add_success
        
    except Exception as e:
        print_error(f"Error handling added criteria: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def handle_update_with_removed_criteria_flow(feature_data, original_feature, criteria_changes):
    """
    Handle feature update where criteria are removed.
    
    Args:
        feature_data (dict): New feature data
        original_feature (dict): Original feature data
        criteria_changes (dict): Analysis of criteria changes
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    feature_id = feature_data['id']
    print_progress(f"Handling feature update with REMOVED criteria for feature: {feature_id}")
    
    # Initialize components
    feature_processor = FeatureProcessor()
    
    try:
        # Repair relationships before making changes
        print_progress(f"Repairing feature-test case relationship before update...")
        repair_result = feature_processor.repair_feature_test_case_relationship(feature_id)
        if repair_result["errors"] > 0:
            print_warning(f"Some errors occurred during relationship repair, but continuing with update")
        
        # Create updated acceptance criteria objects
        updated_criteria_objects = create_updated_criteria_objects(
            original_criteria=original_feature.get('acceptanceCriteria', []),
            criteria_changes=criteria_changes
        )
        
        # Update the feature with new criteria
        feature_update_success = feature_processor.update_feature_with_criteria(
            feature_id=feature_id,
            feature_data=feature_data,
            updated_criteria=updated_criteria_objects,
            preserve_test_cases=True
        )

        if not feature_update_success:
            print_error(f"Failed to update feature with removed criteria")
            return False
        
        # Handle removed criteria
        print_progress(f"Processing {len(criteria_changes['removed'])} removed criteria...")
        removed_criteria_ids = [c.get("id") for c in criteria_changes["removed"]]
        rem_success = await handle_removed_criteria(
            feature_id=feature_id,
            removed_criteria_ids=removed_criteria_ids,
            criteria_map=get_criteria_id_map(updated_criteria_objects)
        )
        
        # Skip consistency check for removed criteria
        print_progress("Skipping criteria status consistency check for removed criteria")
        
        # Final metadata verification
        print_progress(f"Performing final metadata verification...")
        final_fixes = await fix_test_case_metadata_issues(feature_id, fix_null_status=True)
        if final_fixes > 0:
            print_success(f"Fixed metadata issues in {final_fixes} test cases during final verification")
        
        print_success(f"Successfully processed removed criteria for feature: {feature_id}")
        return rem_success
        
    except Exception as e:
        print_error(f"Error handling removed criteria: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def handle_combined_update_flow(feature_data, original_feature, criteria_changes):
    """
    Handle feature update with multiple types of changes (added, modified, and/or removed).
    
    Args:
        feature_data (dict): New feature data
        original_feature (dict): Original feature data
        criteria_changes (dict): Analysis of criteria changes
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    feature_id = feature_data['id']
    print_progress(f"Handling feature update with COMBINED changes for feature: {feature_id}")
    
    # Initialize components
    feature_processor = FeatureProcessor()
    skip_consistency_check = False
    operations = []
    overall_success = True
    
    try:
        # Repair relationships before making changes
        print_progress(f"Repairing feature-test case relationship before update...")
        repair_result = feature_processor.repair_feature_test_case_relationship(feature_id)
        if repair_result["errors"] > 0:
            print_warning(f"Some errors occurred during relationship repair, but continuing with update")
        
        # Create updated acceptance criteria objects
        updated_criteria_objects = create_updated_criteria_objects(
            original_criteria=original_feature.get('acceptanceCriteria', []),
            criteria_changes=criteria_changes
        )
        
        # Update the feature with new criteria
        feature_update_success = feature_processor.update_feature_with_criteria(
            feature_id=feature_id,
            feature_data=feature_data,
            updated_criteria=updated_criteria_objects,
            preserve_test_cases=True
        )

        if not feature_update_success:
            print_error(f"Failed to update feature with combined changes")
            return False
        
        # Handle each type of change
        
        # 1. Handle modified criteria
        if criteria_changes['modified']:
            print_progress(f"Processing {len(criteria_changes['modified'])} modified criteria...")
            mod_success = await handle_modified_criteria(
                feature_id=feature_id,
                modified_criteria=criteria_changes['modified'],
                criteria_map=get_criteria_id_map(updated_criteria_objects)
            )
            operations.append(f"Modified criteria: {'✅ Success' if mod_success else '❌ Failed'}")
            overall_success = overall_success and mod_success
        
        # 2. Handle added criteria
        if criteria_changes['added']:
            print_progress(f"Processing {len(criteria_changes['added'])} added criteria...")
            add_success = await handle_added_criteria(
                feature_id=feature_id,
                feature_data=feature_data,
                added_criteria=criteria_changes['added'],
                updated_criteria_objects=updated_criteria_objects
            )
            operations.append(f"Added criteria: {'✅ Success' if add_success else '❌ Failed'}")
            overall_success = overall_success and add_success
        
        # 3. Handle removed criteria
        if criteria_changes['removed']:
            print_progress(f"Processing {len(criteria_changes['removed'])} removed criteria...")
            removed_criteria_ids = [c.get("id") for c in criteria_changes["removed"]]
            rem_success = await handle_removed_criteria(
                feature_id=feature_id,
                removed_criteria_ids=removed_criteria_ids,
                criteria_map=get_criteria_id_map(updated_criteria_objects)
            )
            operations.append(f"Removed criteria: {'✅ Success' if rem_success else '❌ Failed'}")
            overall_success = overall_success and rem_success
            
            # Skip consistency check for removed criteria
            print_progress("Skipping criteria status consistency check for removed criteria")
            skip_consistency_check = True
        
        # Verify and fix metadata consistency if not skipped
        if not skip_consistency_check:
            print_progress(f"Verifying criteria status consistency...")
            await verify_criteria_status_consistency(feature_id)
        else:
            print_progress(f"Criteria status consistency check skipped for removed criteria")
        
        # Final metadata verification
        print_progress(f"Performing final metadata verification...")
        final_fixes = await fix_test_case_metadata_issues(feature_id, fix_null_status=True)
        if final_fixes > 0:
            print_success(f"Fixed metadata issues in {final_fixes} test cases during final verification")
        
        if operations:
            print_success("Feature update summary:")
            for op in operations:
                print_progress(f"  - {op}")
            
        print_success(f"Feature update workflow completed successfully for {feature_id}")
        return overall_success
        
    except Exception as e:
        print_error(f"Error in combined update workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
