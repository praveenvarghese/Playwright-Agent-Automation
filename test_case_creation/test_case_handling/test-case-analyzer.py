import numpy as np
from datetime import datetime, timezone
from test_case_creation.data_services.embeddings import EmbeddingsGenerator

async def analyze_test_cases_with_embeddings(test_cases, criteria_changes):
    """
    Analyze existing test cases using embedding-based similarity to decide which to keep,
    update, or regenerate when requirements change.
    
    Args:
        test_cases (list): List of existing test cases
        criteria_changes (dict): The criteria change analysis result
        
    Returns:
        dict: Decision for each test case:
            - keep_unchanged: test cases with only unchanged criteria
            - keep_with_updates: test cases to keep but update criteria mappings
            - regenerate: test cases to regenerate
    """
    print("🔹 Analyzing test cases using embedding-based similarity...")
    
    result = {
        "keep_unchanged": [],  # Test cases with only unchanged criteria
        "keep_with_updates": [],  # Test cases with some modified criteria
        "regenerate": []  # Test cases with removed criteria or significant changes
    }
    
    # Initialize embeddings generator
    embeddings_generator = EmbeddingsGenerator()
    
    # Generate embeddings for criteria in each category
    unchanged_embeddings = []
    for criteria in criteria_changes["unchanged"]:
        embedding = embeddings_generator.generate_embedding(criteria.get("description", ""))
        if embedding:
            unchanged_embeddings.append({
                "id": criteria.get("id"),
                "embedding": embedding
            })
    
    modified_embeddings = []
    for original, new_description in criteria_changes["modified"]:
        # Generate embedding for the new description
        embedding = embeddings_generator.generate_embedding(new_description)
        if embedding:
            modified_embeddings.append({
                "id": original.get("id"),
                "embedding": embedding
            })
    
    removed_embeddings = []
    for criteria in criteria_changes["removed"]:
        embedding = embeddings_generator.generate_embedding(criteria.get("description", ""))
        if embedding:
            removed_embeddings.append({
                "id": criteria.get("id"),
                "embedding": embedding
            })
    
    # Analyze each test case
    for test_case in test_cases:
        # Skip already inactive test cases
        if test_case.get("status") == "Inactive":
            continue
            
        # Get criteria metadata for this test case
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        
        if not criteria_metadata:
            # If no criteria metadata, analyze test case content directly
            test_case_id = test_case.get("id", "")
            test_case_content = (
                test_case.get("title", "") + " " + 
                test_case.get("steps", "") + " " + 
                test_case.get("expectedResults", "")
            )
            
            # Generate embedding for test case content
            test_case_embedding = embeddings_generator.generate_embedding(test_case_content)
            if not test_case_embedding:
                print(f"⚠️ Could not generate embedding for test case {test_case_id}, using rule-based decision")
                result["regenerate"].append(test_case)
                continue
            
            # Calculate similarity with each criteria category
            unchanged_similarity = calculate_max_similarity(test_case_embedding, unchanged_embeddings)
            modified_similarity = calculate_max_similarity(test_case_embedding, modified_embeddings)
            removed_similarity = calculate_max_similarity(test_case_embedding, removed_embeddings)
            
            # Make decision based on similarities
            if removed_similarity > 0.8:
                # If highly similar to removed criteria, regenerate
                print(f"🔹 Test case {test_case_id} is highly similar to removed criteria, regenerating")
                result["regenerate"].append(test_case)
            elif modified_similarity > 0.8 and unchanged_similarity < 0.7:
                # If highly similar to modified criteria but not to unchanged, regenerate
                print(f"🔹 Test case {test_case_id} is highly similar to modified criteria, regenerating")
                result["regenerate"].append(test_case)
            elif modified_similarity > 0.7:
                # If somewhat similar to modified criteria, keep with updates
                print(f"🔹 Test case {test_case_id} is somewhat similar to modified criteria, keeping with updates")
                result["keep_with_updates"].append(test_case)
            elif unchanged_similarity > 0.7:
                # If similar to unchanged criteria, keep unchanged
                print(f"🔹 Test case {test_case_id} is similar to unchanged criteria, keeping unchanged")
                result["keep_unchanged"].append(test_case)
            else:
                # If not strongly similar to any category, regenerate
                print(f"🔹 Test case {test_case_id} is not strongly similar to any criteria category, regenerating")
                result["regenerate"].append(test_case)
        else:
            # Use criteria metadata for decisions
            criteria_ids = [c.get("criteriaId") for c in criteria_metadata]
            
            # Check for each criteria category
            has_removed = any(c.get("id") in criteria_ids for c in criteria_changes["removed"])
            has_modified = any(original.get("id") in criteria_ids for original, _ in criteria_changes["modified"])
            has_unchanged = any(c.get("id") in criteria_ids for c in criteria_changes["unchanged"])
            
            # Count criteria in each category
            removed_count = sum(1 for c in criteria_metadata if c.get("criteriaId") in 
                               [rc.get("id") for rc in criteria_changes["removed"]])
            modified_count = sum(1 for c in criteria_metadata if c.get("criteriaId") in 
                                [mc[0].get("id") for mc in criteria_changes["modified"]])
            unchanged_count = sum(1 for c in criteria_metadata if c.get("criteriaId") in 
                                 [uc.get("id") for uc in criteria_changes["unchanged"]])
            total_count = len(criteria_metadata)
            
            # Make decision based on criteria distribution
            if has_removed and removed_count == total_count:
                # If ALL criteria are removed, regenerate
                result["regenerate"].append(test_case)
            elif has_removed and removed_count > total_count / 2:
                # If MAJORITY of criteria are removed, regenerate
                result["regenerate"].append(test_case)
            elif has_modified and not has_unchanged:
                # If only verifies modified criteria, regenerate
                result["regenerate"].append(test_case)
            elif has_modified:
                # If verifies both modified and unchanged criteria, update mappings
                result["keep_with_updates"].append(test_case)
            else:
                # If only verifies unchanged criteria, keep as is
                result["keep_unchanged"].append(test_case)
    
    # Print summary
    print("✅ Test case analysis complete:")
    print(f"   - Keep unchanged: {len(result['keep_unchanged'])}")
    print(f"   - Keep with updates: {len(result['keep_with_updates'])}")
    print(f"   - Regenerate: {len(result['regenerate'])}")
    
    return result

def calculate_max_similarity(embedding, criteria_embeddings):
    """
    Calculate the maximum similarity between a test case embedding and a list of criteria embeddings.
    
    Args:
        embedding (list): Test case embedding
        criteria_embeddings (list): List of criteria embedding objects
        
    Returns:
        float: Maximum similarity score (0-1)
    """
    if not criteria_embeddings:
        return 0.0
        
    max_similarity = 0.0
    
    for criteria in criteria_embeddings:
        similarity = calculate_cosine_similarity(embedding, criteria["embedding"])
        max_similarity = max(max_similarity, similarity)
    
    return max_similarity

def calculate_cosine_similarity(embedding1, embedding2):
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1 (list): First embedding vector
        embedding2 (list): Second embedding vector
        
    Returns:
        float: Cosine similarity (between 0 and 1)
    """
    # Convert to numpy arrays
    a = np.array(embedding1)
    b = np.array(embedding2)
    
    # Calculate cosine similarity
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    # Ensure the result is between 0 and 1
    return max(0.0, min(1.0, similarity))