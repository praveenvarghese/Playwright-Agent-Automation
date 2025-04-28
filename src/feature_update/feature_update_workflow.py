import os
import asyncio
from datetime import datetime, timezone
import json
import re
from src.test_cases.generator import generate_test_cases
from src.vector_search.retrieval import VectorRetrievalSystem
from src.vector_search.embeddings import EmbeddingsGenerator
from src.vector_search.feature_processor import FeatureProcessor
from src.utils.test_case_analyzer import analyze_test_cases_with_embeddings
from src.utils.json_parser import format_steps
import time
   

# Helper functions for message formatting (reusing from test_case_workflow.py)
def print_progress(message): print(f"🔹 {message}")
def print_success(message): print(f"✅ {message}")
def print_warning(message): print(f"⚠️ {message}")
def print_error(message): print(f"❌ {message}")


async def analyze_criteria_changes(original_criteria, new_criteria_list):
    """
    Analyze changes between original and new acceptance criteria.
    Enhanced to use LLM for semantic understanding of requirement changes.
    
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
        "reactivated": []  # New category for previously deprecated criteria being added back
    }
    
    # Debug output
    print(f"🔹 Original criteria count: {len(original_criteria)}")
    print(f"🔹 New criteria count: {len(new_criteria_list)}")
    
    # Separate active and deprecated criteria for better processing
    active_criteria = [c for c in original_criteria if c.get("status", "Active") == "Active"]
    deprecated_criteria = [c for c in original_criteria if c.get("status", "") == "Deprecated"]
    
    print(f"🔹 Active criteria: {len(active_criteria)}")
    print(f"🔹 Deprecated criteria: {len(deprecated_criteria)}")
    
    # Convert lists to lowercase for easier comparison
    active_desc_list = [c.get("description", "").lower().strip() for c in active_criteria]
    deprecated_desc_list = [c.get("description", "").lower().strip() for c in deprecated_criteria]
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
    
    # Step 2: Check if any new criteria match previously deprecated criteria
    matched_deprecated_indices = set()
    
    for i, deprecated in enumerate(deprecated_criteria):
        deprecated_desc_lower = deprecated_desc_list[i]
        
        for j, new_desc_lower in enumerate(new_desc_list):
            if j in matched_new_indices:
                continue
                
            # Check for exact match or high similarity
            if deprecated_desc_lower == new_desc_lower or calculate_text_similarity(deprecated_desc_lower, new_desc_lower) > 0.9:
                # This is a previously deprecated criteria that's being added back
                result["reactivated"].append((deprecated, new_criteria_list[j]))
                matched_deprecated_indices.add(i)
                matched_new_indices.add(j)
                print(f"🔹 Found reactivated criteria: {deprecated.get('id')} - {deprecated_desc_lower[:50]}...")
                break
    
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
    
    # Print summary
    print(f"🔹 Changes detected: {len(result['unchanged'])} unchanged, {len(result['modified'])} modified, " +
          f"{len(result['added'])} added, {len(result['removed'])} removed, {len(result['reactivated'])} reactivated")
    
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
        print(f"❌ Invalid feature data for update")
        return False
    
    print(f"🔹 Starting enhanced update workflow for feature: {feature_data['id']}")
    
    # Initialize components
    feature_processor = FeatureProcessor()
    vector_system = VectorRetrievalSystem()
    
    try:
        # Step 1: Get original feature data
        original_feature = await get_original_feature(feature_data['id'])
        if not original_feature:
            print(f"⚠️ Couldn't find original feature with ID {feature_data['id']}. Will proceed as new feature.")
            return False
        
        print(f"🔹 Repairing feature-test case relationship before update...")
        feature_processor = FeatureProcessor()
        repair_result = feature_processor.repair_feature_test_case_relationship(feature_data['id'])
        if repair_result["errors"] > 0:
            print(f"⚠️ Some errors occurred during relationship repair, but continuing with update")
        
        # Step 2: Analyze acceptance criteria changes
        criteria_changes = await analyze_criteria_changes(
            original_criteria=original_feature.get('acceptanceCriteria', []),
            new_criteria_list=feature_data.get('acceptance_criteria', [])
        )
        
        # Log the analysis results
        print(f"🔹 Acceptance criteria analysis complete:")
        print(f"🔹  - Unchanged: {len(criteria_changes['unchanged'])}")
        print(f"🔹  - Modified: {len(criteria_changes['modified'])}")
        print(f"🔹  - Added: {len(criteria_changes['added'])}")
        print(f"🔹  - Removed: {len(criteria_changes['removed'])}")
        print(f"🔹  - Reactivated: {len(criteria_changes.get('reactivated', []))}")
        
        # Extract IDs of removed criteria for marking as inactive
        removed_criteria_ids = [c.get("id") for c in criteria_changes["removed"]]
        
        # Step 3: Get existing test cases for this feature
        existing_test_cases = await vector_system.retrieve_test_cases_by_feature_id(feature_data['id'])
        print(f"🔹 Found {len(existing_test_cases)} existing test cases for this feature")
        
        await fix_null_status_in_test_cases(feature_data['id'])
        
        # Step 4: Analyze test cases in relation to criteria changes
        test_case_decision = await analyze_test_cases_with_embeddings(existing_test_cases, criteria_changes)
        
        # Log test case decision
        print(f"🔹 Test case analysis complete:")
        print(f"🔹  - Keep unchanged: {len(test_case_decision['keep_unchanged'])}")
        print(f"🔹  - Keep with updates: {len(test_case_decision['keep_with_updates'])}")
        print(f"🔹  - Regenerate: {len(test_case_decision['regenerate'])}")
        print(f"🔹  - Need new test cases for {len(criteria_changes['added'])} new criteria")
        
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
            print(f"⚠️ Failed to update feature with new criteria")
            return False

        # Check for criteria that changed from Deprecated to Active
        reactivated_criteria_ids = []

        if original_feature and "acceptanceCriteria" in original_feature:
            # Find criteria that were Deprecated in original but are Active now
            original_deprecated_ids = [
                c.get("id") for c in original_feature["acceptanceCriteria"]
                if c.get("status") == "Deprecated" and c.get("id")
            ]
            
            # Check which of these are now Active in the updated criteria
            for criteria_id in original_deprecated_ids:
                for criteria in updated_criteria_objects:
                    if criteria.get("id") == criteria_id and criteria.get("status") == "Active":
                        reactivated_criteria_ids.append(criteria_id)
                        print(f"🔹 Detected criteria {criteria_id} changed from Deprecated to Active")
                        break

        # Reactivate criteria in test cases if needed
        if reactivated_criteria_ids:
            print(f"🔹 Reactivating criteria in test cases: {', '.join(reactivated_criteria_ids)}")
            await reactivate_criteria_in_test_cases(
                feature_id=feature_data['id'],
                reactivated_criteria_ids=reactivated_criteria_ids
            )

        # Fix test cases that contain criteria from this feature but don't have feature metadata
        if 'reactivated' in criteria_changes and criteria_changes['reactivated']:
            reactivated_ids = [reactivated[0].get('id') for reactivated in criteria_changes['reactivated']]
            print(f"🔹 Checking for test cases with reactivated criteria but missing feature metadata")
            await fix_missing_feature_metadata(feature_id=feature_data['id'], criteria_ids=reactivated_ids)

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
        
        # Step 7c: Update content for test cases that need updates
        if test_case_decision['keep_with_updates']:
            embeddings_generator = EmbeddingsGenerator()
            # Create a list of criteria changes with old and new versions
            modified_criteria_pairs = []
            for original, new_description in criteria_changes['modified']:
                modified_criteria_pairs.append((original, new_description))
            
            # Update the test case content
            updated_test_cases = await update_test_case_content(
                test_case_decision['keep_with_updates'], 
                modified_criteria_pairs
            )
            
            # Store the updated test cases
            updated_count = 0
            for updated_tc in updated_test_cases:
                success = embeddings_generator.upload_test_case(updated_tc)
                if success:
                    updated_count += 1
                    print(f"✅ Successfully uploaded updated test case {updated_tc.get('id')}")
                else:
                    print(f"⚠️ Failed to upload updated test case {updated_tc.get('id')}")
            
            print(f"✅ Updated content for {updated_count} test cases")

        # Step 7d: Reactivate previously inactive criteria in test cases
        if 'reactivated' in criteria_changes and criteria_changes['reactivated']:
            reactivated_ids = [reactivated[0].get('id') for reactivated in criteria_changes['reactivated']]
            
            # Create mapping of criteria IDs to new descriptions
            new_descriptions = {}
            for deprecated, new_desc in criteria_changes['reactivated']:
                new_descriptions[deprecated.get('id')] = new_desc
            
            await reactivate_criteria_in_test_cases(
                feature_id=feature_data['id'],
                reactivated_criteria_ids=reactivated_ids,
                new_descriptions=new_descriptions
            )
        
        # Step 8: Update test cases that need updates but not regeneration
        if test_case_decision['keep_with_updates']:
            update_success = await update_test_case_criteria_mappings(
                test_cases=test_case_decision['keep_with_updates'],
                criteria_map=get_criteria_id_map(updated_criteria_objects),
                feature_id=feature_data['id']  # Pass the feature ID
            )
            if not update_success:
                print(f"⚠️ Some test cases could not be updated properly")
        
        # Step 9: Generate new test cases if needed
        test_cases_to_regenerate = len(test_case_decision['regenerate']) > 0 or len(criteria_changes['added']) > 0
        
        if test_cases_to_regenerate:
            print(f"🔹 Generating new test cases for modified/added criteria...")
            
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
                    print(f"⚠️ Some new test cases could not be processed properly")
            else:
                print(f"⚠️ No new test cases were generated")
        
        # Verify and fix criteria status consistency
        print(f"🔹 Verifying criteria status consistency...")
        consistency_fixes = await verify_criteria_status_consistency(feature_data['id'])
        if consistency_fixes > 0:
            print(f"🔹 Fixed criteria status in {consistency_fixes} test cases")

        # Final metadata verification
        print(f"🔹 Performing final metadata verification...")
        final_fixes = await fix_test_case_metadata_issues(feature_data['id'], fix_null_status=True)
        if final_fixes > 0:
            print(f"✅ Fixed metadata issues in {final_fixes} test cases during final verification")
            
        print(f"✅ Feature update workflow completed successfully for {feature_data['id']}")
        return True
        
    except Exception as e:
        print(f"❌ Error in feature update workflow: {str(e)}")
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
    
    # 3. Handle reactivated criteria - previously deprecated but now being added back
    for deprecated, new_description in criteria_changes["reactivated"]:
        # Reuse the original ID but update description and status
        reactivated = {
            "id": deprecated.get("id", ""),
            "description": new_description,
            "status": "Active",  # Change from Deprecated to Active
            "addedDate": datetime.now(timezone.utc).isoformat()  # Update timestamp
        }
        updated_criteria.append(reactivated)
        print(f"🔹 Reactivated criteria {deprecated.get('id')} (changed from Deprecated to Active)")
    
    # 4. Add new criteria with new IDs
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
    print(f"🔹 Added {len(criteria_changes['added'])} new criteria")
    
    # 5. Add removed criteria with deprecated status
    for removed in criteria_changes["removed"]:
        # Create with ONLY the fields in the feature schema
        deprecated_criteria = {
            "id": removed.get("id", ""),
            "description": removed.get("description", ""),
            "status": "Deprecated",  # Mark as deprecated
            "addedDate": datetime.now(timezone.utc).isoformat()
        }
        updated_criteria.append(deprecated_criteria)
        print(f"🔹 Marked removed criteria {removed.get('id')} as Deprecated")
    
    # 6. Include already deprecated criteria that weren't reactivated
    for criteria in original_criteria:
        if criteria.get("status", "") == "Deprecated":
            # Check if this deprecated criteria was reactivated
            was_reactivated = any(
                deprecated.get("id") == criteria.get("id") 
                for deprecated, _ in criteria_changes["reactivated"]
            )
            
            if not was_reactivated:
                # Keep it as deprecated but ensure only schema fields are present
                updated_criteria.append({
                    "id": criteria.get("id", ""),
                    "description": criteria.get("description", ""),
                    "status": "Deprecated",
                    "addedDate": criteria.get("addedDate", datetime.now(timezone.utc).isoformat())
                })
                print(f"🔹 Kept existing deprecated criteria {criteria.get('id')}")
    
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
    from config.config import TestCaseAgent, TestCaseCritic, TestCaseOptimizer
    from src.utils.json_parser import format_steps
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    PROMPTS_DIR = os.path.join(PROJECT_ROOT, "prompts")
    LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
    OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"🔹 Updating content of {len(test_cases_to_update)} test cases...")
    updated_test_cases = []
    
    # Load the update prompt
    UPDATE_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_update_prompt.txt")
    try:
        with open(UPDATE_PROMPT_FILE, "r", encoding="utf-8") as f:
            update_prompt_template = f.read()
    except FileNotFoundError:
        print(f"❌ Error: Update prompt file not found at {UPDATE_PROMPT_FILE}")
        return test_cases_to_update  # Return original test cases if prompt file not found
    
    # Load the update critic prompt
    UPDATE_CRITIC_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_update_critic_prompt.txt")
    try:
        with open(UPDATE_CRITIC_PROMPT_FILE, "r", encoding="utf-8") as f:
            update_critic_template = f.read()
    except FileNotFoundError:
        print(f"⚠️ Update critic prompt file not found at {UPDATE_CRITIC_PROMPT_FILE}")
        # Use empty string if file not found - we'll handle this later
        update_critic_template = ""

    # Load the update optimizer prompt
    UPDATE_OPTIMIZER_PROMPT_FILE = os.path.join(PROMPTS_DIR, "test_case_update_optimizer_prompt.txt")
    try:
        with open(UPDATE_OPTIMIZER_PROMPT_FILE, "r", encoding="utf-8") as f:
            update_optimizer_template = f.read()
    except FileNotFoundError:
        print(f"⚠️ Update optimizer prompt file not found at {UPDATE_OPTIMIZER_PROMPT_FILE}")
        # Use empty string if file not found - we'll handle this later
        update_optimizer_template = ""
    
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
                if update_critic_template:
                    critique_prompt = update_critic_template.replace("{current_test_case}", current_test_case)
                    critique_prompt = critique_prompt.replace("{changed_requirements}", changed_requirements)
                else:
                    # Fall back to hardcoded prompt if file not found
                    critique_prompt = f"""
                    You are a test case reviewer. Review this updated test case and ensure it properly reflects the requirement changes.

                    Updated Test Case:
                    ```json
                    {current_test_case}
                    ```

                    The requirements that changed:
                    {changed_requirements}

                    Check for:
                    1. Does the test case title reflect the new requirements?
                    2. Do the test steps implement the new requirements correctly?
                    3. Do the expected results align with the new requirements?
                    4. Is there any inconsistency between title, steps, and expected results?
                    5. Does the test case actually test the new requirements properly?

                    If you find any issues, provide specific feedback about what needs to be fixed.
                    """
                
                # Get critique
                critique = await TestCaseCritic.a_generate_reply(
                    messages=[{"role": "user", "content": critique_prompt}]
                )
                
                # Save critique for debugging
                critique_file = os.path.join(LOGS_DIR, f"update_critique_{test_case_id}_iter{iteration}.txt")
                with open(critique_file, "w", encoding="utf-8") as f:
                    f.write(critique)
                
                # Update the prompt for next iteration
                update_prompt = f"""
                You previously updated this test case:
                ```json
                {current_test_case}
                ```

                However, the critic found these issues:
                {critique}

                Original requirements change:
                {changed_requirements}

                Please fix ALL the issues identified by the critic and provide a fully updated test case. Make sure:
                1. ALL parts of the test case (title, steps, expected results) are updated
                2. ALL parts are consistent with each other
                3. The test case properly implements the NEW requirements

                Return the improved test case in the same JSON format.
                """
                
            except Exception as e:
                print(f"⚠️ Error in update iteration {iteration}: {str(e)}")
                break
        
        # Add optimizer step after the critique-update loops
        try:
            # Create optimizer prompt using template
            if update_optimizer_template:
                optimizer_prompt = update_optimizer_template.replace("{current_test_case}", current_test_case)
                optimizer_prompt = optimizer_prompt.replace("{changed_requirements}", changed_requirements)
            else:
                # Fall back to hardcoded prompt if file not found
                optimizer_prompt = f"""
                You are a Test Case Optimizer. Optimize this test case to ensure it perfectly aligns with the new requirements.

                Test Case:
                ```json
                {current_test_case}
                ```

                The requirements that changed:
                {changed_requirements}

                Your task is to:
                1. Ensure perfect consistency between title, steps, and expected results
                2. Make sure the test case effectively tests the NEW requirements
                3. Polish the language for clarity and precision
                4. Remove any remaining traces of the old requirements
                5. Ensure environment names follow the new format requirements

                Return the optimized test case in the same JSON format.
                """
            
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
    
    # Construct the prompt for semantic comparison
    prompt = f"""
Compare these two acceptance criteria and determine if they have the same meaning or different meanings:

Original: "{original_desc}"
New: "{new_desc}"

Respond with:
1. Are they semantically equivalent (Yes/No)?
2. If different, how significant is the change (Low/Medium/High)?
3. Brief explanation of the difference
    """
    
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


