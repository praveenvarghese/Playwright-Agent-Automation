import os
import json
from datetime import datetime
import numpy as np
from test_case_creation.data_services.embeddings import EmbeddingsGenerator
from test_case_creation.helpers.common_utils import calculate_cosine_similarity
from test_case_creation.feature_management.feature_processor import FeatureProcessor

async def map_test_cases_to_criteria_with_embeddings(parsed_test_cases, acceptance_criteria):
    """
    Map test cases to acceptance criteria using embeddings-based similarity with top-N matching.
    
    Args:
        parsed_test_cases (list): List of parsed test case dictionaries
        acceptance_criteria (list): List of acceptance criteria
        
    Returns:
        dict: Mapping of test case IDs to their criteria metadata
    """
    print("🔹 Mapping test cases to criteria using embeddings-based similarity...")
    
    # Initialize embeddings generator
    embeddings_generator = EmbeddingsGenerator()
    
    # Generate embeddings for all criteria
    criteria_embeddings = []
    for i, criteria in enumerate(acceptance_criteria):
        embedding = embeddings_generator.generate_embedding(criteria)
        if embedding:
            criteria_embeddings.append({
                "id": f"AC-{i+1:03d}",
                "description": criteria,
                "embedding": embedding
            })
    
    print(f"🔹 Generated embeddings for {len(criteria_embeddings)} acceptance criteria")
    
    # Create mapping dictionary
    mapping = {}
    
    # Process each test case
    for test_case in parsed_test_cases:
        test_case_id = test_case.get("id")
        if not test_case_id:
            continue
            
        # Combine relevant fields for embedding
        test_case_text = (
            test_case.get("title", "") + " " + 
            test_case.get("steps", "") + " " + 
            test_case.get("expectedResults", "")
        )
        
        # Generate embedding for test case
        test_case_embedding = embeddings_generator.generate_embedding(test_case_text)
        if not test_case_embedding:
            print(f"⚠️ Failed to generate embedding for test case {test_case_id}")
            continue
        
        # Calculate similarity with all criteria and store in a list
        all_similarities = []
        for criteria in criteria_embeddings:
            similarity = calculate_cosine_similarity(
                test_case_embedding, 
                criteria["embedding"]
            )
            all_similarities.append({
                "criteriaId": criteria["id"],
                "description": criteria["description"], 
                "status": "Active",
                "similarity": similarity
            })
        
        # Sort by similarity (highest first)
        all_similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Take only the top N most similar criteria that meet minimum threshold
        matched_criteria = []
        top_n = 5  # Set this to your desired number
        min_threshold = 0.80  # Set this to your minimum acceptable similarity
        
        # Debug output
        print(f"🔹 Top similarities for test case {test_case_id}:")
        for i, criteria in enumerate(all_similarities[:5]):  # Show top 5 for debugging
            print(f"   - {criteria['criteriaId']}: {criteria['similarity']:.4f} - {criteria['description'][:30]}...")
        
        for criteria in all_similarities[:top_n]:  # Only check top N
            if criteria["similarity"] >= min_threshold:  # Apply minimum threshold
                # Make a copy without the similarity field
                match = {
                    "criteriaId": criteria["criteriaId"],
                    "description": criteria["description"],
                    "status": "Active"
                }
                matched_criteria.append(match)
                print(f"✅ Matched test case {test_case_id} to criteria {criteria['criteriaId']} (similarity: {criteria['similarity']:.4f})")
        
        if matched_criteria:
            mapping[test_case_id] = matched_criteria
            print(f"✅ Mapped test case {test_case_id} to {len(matched_criteria)} criteria")
        else:
            print(f"⚠️ Could not match test case {test_case_id} to any criteria with confidence")
            # Instead of mapping to all criteria, try to find at least one with best effort
            if all_similarities:
                # Take the best match even if below threshold
                best_match = all_similarities[0]
                match = {
                    "criteriaId": best_match["criteriaId"],
                    "description": best_match["description"],
                    "status": "Active"
                }
                mapping[test_case_id] = [match]
                print(f"🔹 Using best effort match for test case {test_case_id}: {best_match['criteriaId']} (similarity: {best_match['similarity']:.4f})")
    
    print(f"✅ Successfully mapped {len(mapping)} test cases to criteria")
    return mapping

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
    import numpy as np
    a = np.array(embedding1)
    b = np.array(embedding2)
    
    # Calculate cosine similarity
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    # Ensure the result is between 0 and 1
    return max(0.0, min(1.0, similarity))

async def map_test_cases_to_feature_criteria(parsed_test_cases, feature_id):
    """
    Map test cases to criteria by getting criteria directly from the feature database.
    Used specifically for mapping test cases created during feature updates with new criteria.
    
    Args:
        parsed_test_cases (list): List of parsed test case dictionaries
        feature_id (str): The feature ID to get criteria from
        
    Returns:
        dict: Mapping of test case IDs to their criteria metadata
    """
    print("🔹 Mapping test cases to criteria using feature database...")
    
    # Import required modules
    from test_case_creation.data_services.embeddings import EmbeddingsGenerator
    from test_case_creation.feature_management.feature_processor import FeatureProcessor
    from test_case_creation.helpers.common_utils import calculate_cosine_similarity
    
    # Initialize components
    embeddings_generator = EmbeddingsGenerator()
    feature_processor = FeatureProcessor()
    
    # Get criteria directly from the feature database
    feature_results = list(feature_processor.search_client.search(
        search_text="",
        filter=f"id eq '{feature_id}'",
        select=["acceptanceCriteria"]
    ))
    
    if not feature_results or not feature_results[0].get("acceptanceCriteria"):
        print("⚠️ Could not find criteria in feature database")
        raise ValueError(f"No criteria found for feature {feature_id}")
        
    # Get criteria from the feature
    criteria_objects = feature_results[0].get("acceptanceCriteria", [])
    print(f"🔹 Found {len(criteria_objects)} criteria in feature database")
    
    # Filter to only active criteria
    active_criteria = [c for c in criteria_objects if c.get("status", "Active") == "Active"]
    print(f"🔹 Using {len(active_criteria)} active criteria for mapping")
    
    # Generate embeddings for criteria
    criteria_embeddings = []
    for criteria_obj in active_criteria:
        criteria_id = criteria_obj.get("id")
        criteria_description = criteria_obj.get("description")
        
        if not criteria_id or not criteria_description:
            continue
            
        embedding = embeddings_generator.generate_embedding(criteria_description)
        if embedding:
            criteria_embeddings.append({
                "id": criteria_id,
                "description": criteria_description,
                "embedding": embedding
            })
    
    # Create mapping dictionary
    mapping = {}
    
    # Process each test case
    for test_case in parsed_test_cases:
        test_case_id = test_case.get("id")
        if not test_case_id:
            continue
            
        # Combine relevant fields for embedding
        test_case_text = (
            test_case.get("title", "") + " " + 
            test_case.get("steps", "") + " " + 
            test_case.get("expectedResults", "")
        )
        
        # Generate embedding for test case
        test_case_embedding = embeddings_generator.generate_embedding(test_case_text)
        if not test_case_embedding:
            print(f"⚠️ Failed to generate embedding for test case {test_case_id}")
            continue
        
        # Calculate similarity with all criteria and store in a list
        all_similarities = []
        for criteria in criteria_embeddings:
            similarity = calculate_cosine_similarity(
                test_case_embedding, 
                criteria["embedding"]
            )
            all_similarities.append({
                "criteriaId": criteria["id"],  # Note: Map from "id" to "criteriaId" for test cases
                "description": criteria["description"], 
                "status": "Active",
                "similarity": similarity
            })
        
        # Sort by similarity (highest first)
        all_similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Take only the top N most similar criteria that meet minimum threshold
        matched_criteria = []
        top_n = 5  # Set this to your desired number
        min_threshold = 0.80  # Set this to your minimum acceptable similarity
        
        # Debug output
        print(f"🔹 Top similarities for test case {test_case_id}:")
        for i, criteria in enumerate(all_similarities[:5]):  # Show top 5 for debugging
            print(f"   - {criteria['criteriaId']}: {criteria['similarity']:.4f} - {criteria['description'][:30]}...")
        
        for criteria in all_similarities[:top_n]:  # Only check top N
            if criteria["similarity"] >= min_threshold:  # Apply minimum threshold
                # Make a copy without the similarity field
                match = {
                    "criteriaId": criteria["criteriaId"],  # Already mapped correctly above
                    "description": criteria["description"],
                    "status": "Active"
                }
                matched_criteria.append(match)
                print(f"✅ Matched test case {test_case_id} to criteria {criteria['criteriaId']} (similarity: {criteria['similarity']:.4f})")
        
        if matched_criteria:
            mapping[test_case_id] = matched_criteria
            print(f"✅ Mapped test case {test_case_id} to {len(matched_criteria)} criteria")
        else:
            # No fallback - if no matches found, raise an exception
            print(f"❌ Could not match test case {test_case_id} to any criteria with confidence")
            raise ValueError(f"No criteria matches found for test case {test_case_id}")
    
    print(f"✅ Successfully mapped {len(mapping)} test cases to criteria")
    return mapping 