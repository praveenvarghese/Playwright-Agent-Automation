import os
import asyncio
from datetime import datetime, timezone
import json
import re
from src.test_cases.generator import generate_test_cases
from src.vector_search.retrieval import VectorRetrievalSystem
from src.vector_search.embeddings import EmbeddingsGenerator
from src.vector_search.feature_processor import FeatureProcessor

# Helper functions for message formatting (reusing from test_case_workflow.py)
def print_progress(message): print(f"🔹 {message}")
def print_success(message): print(f"✅ {message}")
def print_warning(message): print(f"⚠️ {message}")
def print_error(message): print(f"❌ {message}")


def analyze_criteria_changes(original_criteria, new_criteria_list):
    """
    Analyze changes between original and new acceptance criteria.
    Enhanced to better detect removed criteria.
    
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
        "removed": []
    }
    
    # Debug output
    print_progress(f"Original criteria count: {len(original_criteria)}")
    print_progress(f"New criteria count: {len(new_criteria_list)}")
    
    # Convert lists to lowercase for easier comparison
    original_desc_list = [c.get("description", "").lower().strip() for c in original_criteria]
    new_desc_list = [desc.lower().strip() for desc in new_criteria_list]
    
    # Print criteria for debugging
    print_progress("Original criteria:")
    for i, desc in enumerate(original_desc_list):
        print_progress(f"  {i+1}. {desc[:50]}...")
    
    print_progress("New criteria:")
    for i, desc in enumerate(new_desc_list):
        print_progress(f"  {i+1}. {desc[:50]}...")
    
    # First pass: find exact matches (unchanged)
    matched_indices = set()
    matched_new_indices = set()
    
    for i, original in enumerate(original_criteria):
        original_desc_lower = original.get("description", "").lower().strip()
        
        for j, new_desc_lower in enumerate(new_desc_list):
            if original_desc_lower == new_desc_lower and j not in matched_new_indices:
                result["unchanged"].append(original)
                matched_indices.add(i)
                matched_new_indices.add(j)
                break
    
    # Second pass: find similar criteria (modified)
    for i, original in enumerate(original_criteria):
        if i in matched_indices:
            continue
            
        original_desc_lower = original.get("description", "").lower().strip()
        
        best_match_idx = -1
        best_match_score = 0.7  # Minimum similarity threshold
        
        for j, new_desc_lower in enumerate(new_desc_list):
            if j in matched_new_indices:
                continue
                
            score = calculate_text_similarity(original_desc_lower, new_desc_lower)
            
            if score > best_match_score:
                best_match_score = score
                best_match_idx = j
        
        if best_match_idx >= 0:
            result["modified"].append((original, new_criteria_list[best_match_idx]))
            matched_indices.add(i)
            matched_new_indices.add(best_match_idx)
    
    # Explicitly check for removed criteria
    for i, original in enumerate(original_criteria):
        if i not in matched_indices:
            result["removed"].append(original)
            print_progress(f"Detected removed criteria: {original.get('description', '')[:50]}...")
    
    # Add remaining new criteria as added
    for j, new_desc in enumerate(new_criteria_list):
        if j not in matched_new_indices:
            result["added"].append(new_desc)
            print_progress(f"Detected added criteria: {new_desc[:50]}...")
    
    # Print summary
    print_progress(f"Changes detected: {len(result['unchanged'])} unchanged, {len(result['modified'])} modified, {len(result['added'])} added, {len(result['removed'])} removed")
    
    return result

# Enhanced update_feature_workflow function for updating feature and managing test case status

async def update_feature_workflow(feature_data):
    """
    Enhanced workflow for updating an existing feature.
    Handles test case status updates based on criteria changes.
    
    Args:
        feature_data (dict): The processed feature data with the update
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not feature_data or not feature_data.get('id'):
        print_error("Invalid feature data for update")
        return False
    
    print_progress(f"Starting enhanced update workflow for feature: {feature_data['id']}")
    
    # Initialize components
    feature_processor = FeatureProcessor()
    vector_system = VectorRetrievalSystem()
    
    try:
        # Step 1: Get original feature data
        original_feature = await get_original_feature(feature_data['id'])
        if not original_feature:
            print_warning(f"Couldn't find original feature with ID {feature_data['id']}. Will proceed as new feature.")
            return False
        
        # Step 2: Analyze acceptance criteria changes
        criteria_changes = analyze_criteria_changes(
            original_criteria=original_feature.get('acceptanceCriteria', []),
            new_criteria_list=feature_data.get('acceptance_criteria', [])
        )
        
        # Log the analysis results
        print_progress(f"Acceptance criteria analysis complete:")
        print_progress(f"  - Unchanged: {len(criteria_changes['unchanged'])}")
        print_progress(f"  - Modified: {len(criteria_changes['modified'])}")
        print_progress(f"  - Added: {len(criteria_changes['added'])}")
        print_progress(f"  - Removed: {len(criteria_changes['removed'])}")
        
        # Extract IDs of removed criteria for marking as inactive
        removed_criteria_ids = [c.get("id") for c in criteria_changes["removed"]]
        
        # Step 3: Get existing test cases for this feature
        existing_test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_data['id'])
        print_progress(f"Found {len(existing_test_cases)} existing test cases for this feature")
        
        # Step 4: Analyze test cases in relation to criteria changes
        test_case_decision = analyze_test_cases(existing_test_cases, criteria_changes)
        
        # Log test case decision
        print_progress(f"Test case analysis complete:")
        print_progress(f"  - Keep unchanged: {len(test_case_decision['keep_unchanged'])}")
        print_progress(f"  - Keep with updates: {len(test_case_decision['keep_with_updates'])}")
        print_progress(f"  - Regenerate: {len(test_case_decision['regenerate'])}")
        print_progress(f"  - Need new test cases for {len(criteria_changes['added'])} new criteria")
        
        # Step 5: Create updated acceptance criteria objects
        updated_criteria_objects = create_updated_criteria_objects(
            original_criteria=original_feature.get('acceptanceCriteria', []),
            criteria_changes=criteria_changes
        )
        
        # Step 6: Update the feature with new criteria
        feature_update_success = feature_processor.update_feature_with_criteria(
            feature_id=feature_data['id'],
            feature_data=feature_data,
            updated_criteria=updated_criteria_objects,
            preserve_test_cases=True
        )
        
        if not feature_update_success:
            print_error("Failed to update feature with new criteria")
            return False
        
        # Step 7a: Mark criteria as inactive in test cases that will be kept
        if removed_criteria_ids:
            await mark_deprecated_criteria_in_test_cases(
                feature_id=feature_data['id'],
                removed_criteria_ids=removed_criteria_ids,
                keep_test_cases=test_case_decision['keep_unchanged'] + test_case_decision['keep_with_updates']
            )
        
        # Step 7b: Mark test cases that need regeneration as inactive
        if test_case_decision['regenerate']:
            regenerate_ids = [tc.get('id') for tc in test_case_decision['regenerate']]
            await mark_test_cases_inactive(
                feature_id=feature_data['id'],
                test_case_ids=regenerate_ids,
                reason="Criteria removed or significantly changed"
            )
        
        # Step 8: Update test cases that need updates but not regeneration
        if test_case_decision['keep_with_updates']:
            update_success = await update_test_case_criteria_mappings(
                test_cases=test_case_decision['keep_with_updates'],
                criteria_map=get_criteria_id_map(updated_criteria_objects)
            )
            if not update_success:
                print_warning("Some test cases could not be updated properly")
        
        # Step 9: Generate new test cases if needed
        test_cases_to_regenerate = len(test_case_decision['regenerate']) > 0 or len(criteria_changes['added']) > 0
        
        if test_cases_to_regenerate:
            print_progress("Generating new test cases for modified/added criteria...")
            
            # Prepare context using existing test cases
            context_test_cases = test_case_decision['keep_unchanged'] + test_case_decision['keep_with_updates']
            
            # Generate requirements-specific text for new test cases
            requirement_text = await generate_requirement_text(
                feature_data, criteria_changes['added'], criteria_changes['modified']
            )
            
            # Generate new test cases
            new_test_cases_content = await generate_selective_test_cases(
                requirement_text, context_test_cases, criteria_changes
            )
            
            if new_test_cases_content:
                # Process and store the new test cases with feature relation
                process_success = await process_and_store_selective_test_cases(
                    new_test_cases_content, feature_data, updated_criteria_objects
                )
                if not process_success:
                    print_warning("Some new test cases could not be processed properly")
            else:
                print_warning("No new test cases were generated")
        
        print_success(f"Feature update workflow completed successfully for {feature_data['id']}")
        return True
        
    except Exception as e:
        print_error(f"Error in feature update workflow: {str(e)}")
        # Log the full error with traceback
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
    """
    Create updated acceptance criteria objects with preserved IDs where possible.
    
    Args:
        original_criteria (list): List of original criteria objects
        criteria_changes (dict): The criteria change analysis result
        
    Returns:
        list: Updated list of criteria objects with IDs
    """
    updated_criteria = []
    
    # 1. Add unchanged criteria as they are
    updated_criteria.extend(criteria_changes["unchanged"])
    
    # 2. Add modified criteria with updated descriptions but preserved IDs
    for original, new_description in criteria_changes["modified"]:
        # Create a copy of the original criteria object
        updated = dict(original)
        # Update the description
        updated["description"] = new_description
        # Update the status if needed
        updated["status"] = "Active"
        # Add last updated timestamp
        updated["addedDate"] = datetime.now(timezone.utc).isoformat()
        updated_criteria.append(updated)
    
    # 3. Add new criteria with new IDs
    next_id = 1
    # Find the highest existing ID number
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
    
    # 4. Add removed criteria with deprecated status if needed
    for removed in criteria_changes["removed"]:
        # Create a copy of the removed criteria object
        updated = dict(removed)
        # Update the status
        updated["status"] = "Deprecated"
        # Add removed date timestamp
        updated["removedDate"] = datetime.now(timezone.utc).isoformat()
        updated_criteria.append(updated)
    
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
            description = criteria.get("description", "").lower().strip()
            criteria_map[description] = criteria
    
    return criteria_map

async def update_test_case_criteria_mappings(test_cases, criteria_map):
    """
    Update criteria mappings for test cases that need updates.
    
    Args:
        test_cases (list): Test cases to update
        criteria_map (dict): Mapping of criteria descriptions to objects
        
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
            if description in criteria_map:
                # Update to the latest criteria
                updated_metadata.append({
                    "criteriaId": criteria_map[description]["id"],
                    "description": criteria_map[description]["description"]
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
                        "description": best_match["description"]
                    })
                else:
                    # If no good match, keep the original but mark it
                    print_warning(f"No match found for criteria: {description}")
                    updated_metadata.append(criteria)
        
        # Update the test case if metadata changed
        if updated_metadata != criteria_metadata:
            test_case["criteriaMetadata"] = updated_metadata
            success = embeddings_generator.upload_test_case(test_case)
            if success:
                update_count += 1
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
    prompt_file = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")), 
                             "prompts", "generator_prompt.txt")
    
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        print_error(f"Generator prompt template not found at {prompt_file}")
        # Create a minimal template
        template = """As an expert test case designer, create simplified test cases for a web-based application with the following requirements:

Requirement Specification
Description
{description}

Acceptance Criteria
{criteria}

For each identified requirement, generate 2 simple test cases that include only:

1. Test Case ID: TC-{prefix}-[Number]
2. Test Case Title: Clear, action-oriented title
3. Test Steps: Numbered, specific user actions (no more than 5 steps per test case)
4. Expected Results: Observable outcomes

Focus on the most basic, core functionality test cases. Do not include preconditions, test data, assertion points, or test categories. Keep the test cases simple and straightforward."""
    
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
    from src.test_cases.generator import generate_test_cases
    
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
    from src.core.test_case_workflow import process_and_store_test_cases
    
    # Process the test cases using the existing function
    success = await process_and_store_test_cases(test_cases_content, feature_data)
    
    return success

async def clean_deprecated_criteria_references(feature_id, removed_criteria_ids):
    """
    Explicitly remove references to deprecated criteria from all test cases.
    This ensures test cases don't maintain links to criteria that have been removed.
    
    Args:
        feature_id (str): The feature ID
        removed_criteria_ids (list): List of criteria IDs that were removed
        
    Returns:
        int: Number of test cases updated
    """
    if not removed_criteria_ids:
        print_progress("No criteria were removed, no cleanup needed")
        return 0
        
    print_progress(f"Cleaning up references to {len(removed_criteria_ids)} removed criteria from test cases")
    
    # Initialize vector system and embeddings generator
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    # Get all test cases for this feature
    test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    updated_count = 0
    
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        # Check if this test case references any removed criteria
        original_count = len(criteria_metadata)
        updated_metadata = [
            criteria for criteria in criteria_metadata
            if criteria.get("criteriaId") not in removed_criteria_ids
        ]
        
        # If criteria were removed, update the test case
        if len(updated_metadata) < original_count:
            print_progress(f"Removing deprecated criteria references from test case {test_case_id}")
            test_case["criteriaMetadata"] = updated_metadata
            
            # Upload the updated test case
            success = embeddings_generator.upload_test_case(test_case)
            if success:
                updated_count += 1
                print_success(f"Successfully updated test case {test_case_id}")
            else:
                print_warning(f"Failed to update test case {test_case_id}")
    
    print_success(f"Cleaned up criteria references in {updated_count} test cases")
    return updated_count

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
    Mark references to deprecated criteria as inactive in test cases,
    rather than removing them completely.
    
    Args:
        feature_id (str): The feature ID
        removed_criteria_ids (list): List of criteria IDs that were removed
        keep_test_cases (list): Optional list of test cases to process (if not all)
        
    Returns:
        int: Number of test cases updated
    """
    if not removed_criteria_ids:
        print_progress("No criteria were removed, no cleanup needed")
        return 0
        
    print_progress(f"Marking {len(removed_criteria_ids)} removed criteria as inactive in test cases")
    
    # Initialize vector system and embeddings generator
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    # Get test cases to process
    test_cases = keep_test_cases or await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    updated_count = 0
    
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        # Check if this test case references any removed criteria
        updated = False
        for criteria in criteria_metadata:
            if criteria.get("criteriaId") in removed_criteria_ids:
                # Mark as inactive
                criteria["status"] = "Inactive"
                criteria["removedDate"] = datetime.now(timezone.utc).isoformat()
                updated = True
                print_progress(f"Marked criteria {criteria.get('criteriaId')} as inactive in test case {test_case_id}")
        
        # If criteria were marked as inactive, update the test case
        if updated:
            # Add a note about criteria changes to the test case
            # if "notes" not in test_case:
            #     test_case["notes"] = ""
            
            # removed_criteria_ids_str = ", ".join(removed_criteria_ids)
            # test_case["notes"] += f"[{datetime.now().strftime('%Y-%m-%d')}] Criteria marked inactive: {removed_criteria_ids_str}\n"
            # test_case["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            
            # Upload the updated test case
            if "featureMetadata" in test_case:
                test_case["featureMetadata"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            success = embeddings_generator.upload_test_case(test_case)
            if success:
                updated_count += 1
                print_success(f"Successfully updated test case {test_case_id}")
            else:
                print_warning(f"Failed to update test case {test_case_id}")
    
    print_success(f"Marked deprecated criteria as inactive in {updated_count} test cases")
    return updated_count

async def mark_test_case_deprecated(test_case_id, reason="Feature deprecated", replacement_id=None):
    """
    Mark a test case as deprecated, which is a step before making it inactive.
    
    Args:
        test_case_id (str): The test case ID to mark as deprecated
        reason (str): Reason for deprecation
        replacement_id (str): Optional ID of the replacement test case
        
    Returns:
        bool: True if successful, False otherwise
    """
    embeddings_generator = EmbeddingsGenerator()
    
    try:
        # Search for the test case
        results = list(embeddings_generator.search_client.search(
            search_text="",
            filter=f"id eq '{test_case_id}'",
            select=["*"]
        ))
        
        if not results:
            print_warning(f"Test case {test_case_id} not found")
            return False
            
        test_case = dict(results[0])
        
        # Update the test case status
        test_case["status"] = "Deprecated"
        test_case["lastUpdated"] = datetime.now(timezone.utc).isoformat()
        test_case["statusReason"] = reason
        
        # Add a reference to the replacement if provided
        if replacement_id:
            test_case["replacedBy"] = replacement_id
        
        # Upload the updated test case
        success = embeddings_generator.upload_test_case(test_case)
        
        if success:
            print_success(f"Successfully marked test case {test_case_id} as deprecated")
            return True
        else:
            print_warning(f"Failed to update test case {test_case_id}")
            return False
            
    except Exception as e:
        print_error(f"Error updating test case {test_case_id}: {str(e)}")
        return False

async def archive_test_cases(feature_id, reason="Feature archived"):
    """
    Archive all test cases for a feature.
    Used when a feature is completely removed or archived.
    
    Args:
        feature_id (str): The feature ID
        reason (str): Reason for archiving
        
    Returns:
        int: Number of test cases archived
    """
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    # Get all test cases for this feature
    test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_id)
    archived_count = 0
    
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        
        # Update the test case status
        test_case["status"] = "Archived"
        # test_case["lastUpdated"] = datetime.now(timezone.utc).isoformat()
        # test_case["statusReason"] = reason
        # test_case["archivedDate"] = datetime.now(timezone.utc).isoformat()
        if "featureMetadata" in test_case:
            test_case["featureMetadata"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
        # Upload the updated test case
        success = embeddings_generator.upload_test_case(test_case)
        
        if success:
            archived_count += 1
            print_success(f"Successfully archived test case {test_case_id}")
        else:
            print_warning(f"Failed to archive test case {test_case_id}")
    
    print_success(f"Archived {archived_count} test cases for feature {feature_id}")
    return archived_count