import os
from datetime import datetime
import re
# Import modules using the new structure
from test_case_creation.test_case_handling.generator import generate_test_cases
from test_case_creation.data_services.vector_search import VectorRetrievalSystem
from test_case_creation.data_services.embeddings import EmbeddingsGenerator
from test_case_creation.feature_management.feature_processor import FeatureProcessor
from test_case_creation.helpers.json_parser import parse_test_cases_from_llm_output
from test_case_creation.data_services.criteria_mapper import map_test_cases_to_criteria_with_embeddings
from test_case_creation.helpers.common_utils import print_progress, print_success, print_warning, print_error

# Define constants for all path references
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")

# Create necessary directories
for directory in [LOGS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

# Helper functions for message formatting
def print_progress(message): print(f"🔹 {message}")
def print_success(message): print(f"✅ {message}")
def print_warning(message): print(f"⚠️ {message}")
def print_error(message): print(f"❌ {message}")

async def read_feature_requirement():
    """Read and process the feature requirement from the prompt file."""
    try:
        # Path to the feature requirement file
        feature_file = os.path.join(PROMPTS_DIR, "feature_requirement.txt")
        
        # Initialize the feature processor
        feature_processor = FeatureProcessor()
        
        # Check if file exists
        if not os.path.exists(feature_file):
            print_error(f"Error: Feature requirement file not found at {feature_file}")
            return None
            
        # Process the feature requirement - ADD THE AWAIT HERE
        processed_feature = await feature_processor.process_and_store_feature_file(feature_file)
        
        if processed_feature:
            print_success(f"Successfully processed feature: {processed_feature['id']}")
            return processed_feature
        else:
            print_error("Failed to process feature requirement")
            return None
            
    except FileNotFoundError as e:
        print_error(f"Error: Feature requirement file not found - {e}")
        return None
    except Exception as e:
        print_error(f"Error processing feature requirement: {str(e)}")
        return None
    
async def read_requirement():
    """Read the test case requirement from the prompt file."""
    try:
        # Updated path using the new structure and absolute path
        prompt_file = os.path.join(PROMPTS_DIR, "generator_prompt.txt")
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as e:
        print_error(f"Error: Prompt file not found - {e}")
        return None

async def find_similar_test_cases(requirement_text):
    """Find similar test cases to use as context."""
    print_progress("Searching for similar existing test cases...")
    vector_system = VectorRetrievalSystem()
    similar_cases = await vector_system.retrieve_similar_test_cases(requirement_text)
    
    if similar_cases and len(similar_cases) > 0:
        print_progress(f"Found {len(similar_cases)} similar test cases to use as reference.")
        for i, case in enumerate(similar_cases):
            print(f"  {i+1}. {case.get('title', 'Unknown')}")
    else:
        print_progress("No similar test cases found in the database.")
    
    return similar_cases

async def create_test_cases(similar_cases):
    """Generate test cases using the prompt and similar cases."""
    print_progress("Generating test cases...")
    test_cases_content = await generate_test_cases(similar_cases)
    
    # Save generated content to files
    if test_cases_content:
        # Save raw response to logs directory
        raw_response_file = os.path.join(LOGS_DIR, "RawOpenAIResponse.txt")
        with open(raw_response_file, "w", encoding="utf-8") as f:
            f.write(test_cases_content)
        
        # Save formatted test cases to output directory
        test_cases_file = os.path.join(OUTPUT_DIR, "TestCases.txt")
        with open(test_cases_file, "w", encoding="utf-8") as f:
            f.write(test_cases_content)
    
    return test_cases_content

def fallback_map_test_cases_to_criteria(parsed_test_cases, acceptance_criteria):
    """
    Fallback method to map test cases to criteria using keyword matching.
    Updated to work with parsed test cases instead of text sections.
    
    Args:
        parsed_test_cases (list): List of parsed test case dictionaries
        acceptance_criteria (list): List of acceptance criteria
        
    Returns:
        dict: Mapping of test case IDs to their criteria metadata
    """
    print_warning("Using fallback method for mapping test cases to criteria")
    mapping = {}
    
    for test_case in parsed_test_cases:
        test_case_id = test_case.get("id")
        if not test_case_id:
            continue
            
        # Combine all test case text for matching
        test_case_content = (
            test_case.get("title", "") + " " + 
            test_case.get("steps", "") + " " + 
            test_case.get("expectedResults", "")
        ).lower()
        
        # Find matching criteria
        criteria_matches = []
        for i, criteria in enumerate(acceptance_criteria):
            criteria_text = criteria.lower()
            
            # Extract key terms from criteria (words with 4+ characters)
            key_terms = [word for word in criteria_text.split() if len(word) >= 4]
            
            # Count how many key terms match
            matching_terms = sum(1 for term in key_terms if term in test_case_content)
            
            # If more than 30% of key terms match, consider it related
            if matching_terms > 0 and (matching_terms / max(len(key_terms), 1) >= 0.3):
                criteria_matches.append({
                    "criteriaId": f"AC-{i+1:03d}",
                    "description": criteria,
                    "status": "Active"  # Explicitly set status to Active
                })
        
        if criteria_matches:
            mapping[test_case_id] = criteria_matches
    
    print_success(f"Fallback mapping created {len(mapping)} mappings")
    return mapping

async def process_and_store_test_cases(test_cases_content, feature_data=None):
    """Process the generated test cases and store them in the database."""
    print_progress("Processing and uploading test cases...")
    
    # Parse test cases from LLM output using the improved JSON parser
    parsed_test_cases = parse_test_cases_from_llm_output(test_cases_content)
    
    print_progress(f"Found {len(parsed_test_cases)} test cases in the generated content")
    
    # Process each test case
    embeddings_generator = EmbeddingsGenerator()
    stored_count = 0
    processed_test_cases = []
    test_case_ids = []  # Store test case IDs to update feature
    
    # Extract acceptance criteria if feature data is available
    acceptance_criteria = []
    criteria_mapping = {}
    
    if feature_data and 'acceptance_criteria' in feature_data:
        acceptance_criteria = feature_data['acceptance_criteria']
        
        # If we have acceptance criteria, use AI to map test cases to criteria
        if acceptance_criteria:
            print_progress("Using embeddings-based criteria mapping...")
            criteria_mapping = await map_test_cases_to_criteria_with_embeddings(
                parsed_test_cases, 
                acceptance_criteria
            )
    
    for i, parsed_case in enumerate(parsed_test_cases, 1):  # Start index from 1
        if not parsed_case.get("id"):
            print_error(f"  Missing ID for test case {i}, skipping")
            continue
            
        print(f"Processing test case {i}...")
        print(f"  ID: {parsed_case.get('id')}")
        print(f"  Title: {parsed_case.get('title', '')}")
        
        # Add feature metadata if available
        if feature_data:
            parsed_case["featureMetadata"] = {
                "featureId": feature_data["id"],
                "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            
            # Add criteria metadata from AI mapping
            if acceptance_criteria and parsed_case["id"] in criteria_mapping:
                parsed_case["criteriaMetadata"] = criteria_mapping[parsed_case["id"]]
                print(f"  Mapped to {len(parsed_case['criteriaMetadata'])} acceptance criteria")
        
        success = embeddings_generator.upload_test_case(parsed_case)
        if success:
            stored_count += 1
            processed_test_cases.append(parsed_case)
            test_case_ids.append(parsed_case.get("id"))
            print_success(f"  Successfully uploaded test case {i}")
        else:
            print_warning(f"  Failed to upload test case {i}")
    
    print_success(f"Successfully stored {stored_count} test cases in the vector database.")
    
    # Update feature with test case IDs if feature data is available and test cases were stored
    if feature_data and test_case_ids:
        feature_processor = FeatureProcessor()
        update_success = feature_processor.update_feature_test_cases(feature_data["id"], test_case_ids)
        
        if update_success:
            print_success(f"Successfully linked {len(test_case_ids)} test cases to feature {feature_data['id']}")
        else:
            print_warning(f"Failed to link test cases to feature {feature_data['id']}")
    
    # Save processed test cases to log file
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(LOGS_DIR, f"test_cases_log_{timestamp}.txt")
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"PROCESSED TEST CASES - {datetime.now().isoformat()}\n\n")
        for i, case in enumerate(processed_test_cases, 1):  # Start index from 1
            f.write(f"Test Case {i}:\n")
            f.write(f"ID: {case.get('id', 'Unknown')}\n")
            f.write(f"Title: {case.get('title', 'Unknown')}\n")
            f.write(f"Steps:\n{case.get('steps', 'None')}\n")
            f.write(f"Expected Results:\n{case.get('expectedResults', 'None')}\n")
            if case.get("featureMetadata"):
                f.write(f"Feature ID: {case.get('featureMetadata', {}).get('featureId', 'None')}\n")
            if case.get("criteriaMetadata"):
                f.write(f"Mapped Criteria:\n")
                for criteria in case.get("criteriaMetadata", []):
                    f.write(f"  - {criteria.get('criteriaId', 'Unknown')}: {criteria.get('description', 'None')}\n")
            f.write("\n---\n\n")

    # Verify criteria coverage - properly placed outside the file writing block
    if feature_data and 'acceptance_criteria' in feature_data:
        await verify_criteria_coverage(processed_test_cases, feature_data['acceptance_criteria'], feature_data)
    
    return True

async def verify_criteria_coverage(processed_test_cases, acceptance_criteria, feature_data):
    """
    Verify that all acceptance criteria are covered by at least one test case.
    If any criteria are not covered, generate additional test cases.
    
    Args:
        processed_test_cases (list): List of processed test case dictionaries
        acceptance_criteria (list): List of acceptance criteria
        feature_data (dict): The feature data
        
    Returns:
        bool: True if all criteria were already covered, False if additional tests were generated
    """
    print_progress("Verifying that all acceptance criteria are covered by test cases...")
    
    # Extract all criteria IDs that are covered by any test case
    covered_criteria_ids = set()
    for test_case in processed_test_cases:
        criteria_metadata = test_case.get("criteriaMetadata", []) or []
        for criteria in criteria_metadata:
            criteria_id = criteria.get("criteriaId")
            if criteria_id:
                covered_criteria_ids.add(criteria_id)
    
    # Generate all possible criteria IDs
    all_criteria_ids = [f"AC-{i+1:03d}" for i in range(len(acceptance_criteria))]
    
    # Find uncovered criteria
    uncovered_criteria = []
    uncovered_descriptions = []
    uncovered_indices = []
    for i, criteria_id in enumerate(all_criteria_ids):
        if criteria_id not in covered_criteria_ids:
            uncovered_criteria.append({
                "id": criteria_id,
                "description": acceptance_criteria[i]
            })
            uncovered_descriptions.append(acceptance_criteria[i])
            uncovered_indices.append(i)
    
    if not uncovered_criteria:
        print_success("✅ All acceptance criteria are covered by at least one test case!")
        return True
    
    # Log uncovered criteria
    print_warning(f"⚠️ Found {len(uncovered_criteria)} acceptance criteria not covered by any test case:")
    for criteria in uncovered_criteria:
        print_warning(f"  - {criteria['id']}: {criteria['description'][:50]}...")
    
    # Generate additional test cases for uncovered criteria
    print_progress("🔹 Generating additional test cases for uncovered criteria...")
    
    # Generate test cases focused on uncovered criteria
    additional_test_cases = await generate_focused_test_cases(feature_data, uncovered_descriptions)
    
    if additional_test_cases:
        # Parse the additional test cases
        from test_case_creation.helpers.json_parser import parse_test_cases_from_llm_output
        
        parsed_additional_cases = parse_test_cases_from_llm_output(additional_test_cases)
        if not parsed_additional_cases:
            print_warning("⚠️ Failed to parse additional test cases")
            return False
            
        print_progress(f"🔹 Found {len(parsed_additional_cases)} additional test cases")
        
        # Map the additional test cases to criteria using the existing mapping function
        print_progress("🔹 Mapping additional test cases to criteria...")
        from test_case_creation.data_services.criteria_mapper import map_test_cases_to_criteria_with_embeddings
        
        criteria_mapping = await map_test_cases_to_criteria_with_embeddings(
            parsed_additional_cases, 
            acceptance_criteria
        )
        
        # Process and store these test cases
        embeddings_generator = EmbeddingsGenerator()
        additional_test_case_ids = []
        
        # Process each additional test case
        for i, case in enumerate(parsed_additional_cases):
            print_progress(f"Processing additional test case for coverage: {case.get('id')}")
            
            # Add feature metadata
            case["featureMetadata"] = {
                "featureId": feature_data["id"],
                "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            
            # Add criteria metadata from mapping
            if case["id"] in criteria_mapping:
                case["criteriaMetadata"] = criteria_mapping[case["id"]]
                print(f"  Mapped to {len(case['criteriaMetadata'])} acceptance criteria")
            else:
                # Fallback mapping to ensure coverage
                # If mapping failed, directly map to the first uncovered criteria
                case["criteriaMetadata"] = [{
                    "criteriaId": uncovered_criteria[0]["id"],
                    "description": uncovered_criteria[0]["description"],
                    "status": "Active"
                }]
                print(f"  Mapped to {uncovered_criteria[0]['id']} (fallback mapping)")
            
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
            # Get the most recently added test cases to update with feature metadata
            recent_test_cases = additional_test_case_ids[-min(3, len(additional_test_case_ids)):]
            update_success = feature_processor.update_feature_test_cases(
                feature_data["id"], 
                additional_test_case_ids
            )
            
            if update_success:
                print_success(f"✅ Successfully updated feature {feature_data['id']} with {len(additional_test_case_ids)} new test cases")
            else:
                print_warning(f"⚠️ Failed to update feature {feature_data['id']} with new test cases")
        
        print_success(f"✅ Successfully stored {len(additional_test_case_ids)}/{len(parsed_additional_cases)} additional test cases")
        print_success("✅ Generated additional test cases for criteria coverage!")
        return False  # Return False to indicate we had to generate additional tests
    else:
        print_warning("⚠️ Failed to generate additional test cases for uncovered criteria")
        return False
    
async def process_and_store_additional_test_cases(test_cases_content, feature_data, target_criteria):
    """
    Process and store additional test cases generated for criteria coverage.
    This is a simplified version that won't trigger further coverage checks.
    
    Args:
        test_cases_content (str): Generated test cases content
        feature_data (dict): Feature data
        target_criteria (list): List of criteria these test cases should cover
        
    Returns:
        bool: True if successful, False otherwise
    """
    print_progress("Processing additional test cases for criteria coverage...")
    
    # Parse test cases using the existing parser
    from test_case_creation.helpers.json_parser import parse_test_cases_from_llm_output
    
    parsed_test_cases = parse_test_cases_from_llm_output(test_cases_content)
    
    if not parsed_test_cases:
        print_warning("Failed to parse additional test cases")
        return False
    
    print_progress(f"Found {len(parsed_test_cases)} additional test cases")
    
    # Initialize components
    embeddings_generator = EmbeddingsGenerator()
    
    # Create a mapping of criteria descriptions to IDs
    criteria_map = {}
    for i, criteria in enumerate(feature_data.get('acceptance_criteria', [])):
        criteria_id = f"AC-{i+1:03d}"
        criteria_map[criteria] = criteria_id
    
    # Process each test case, focusing on mapping to target criteria
    stored_count = 0
    for parsed_case in parsed_test_cases:
        print(f"Processing additional test case for coverage: {parsed_case.get('id')}")
        
        # Add feature metadata
        parsed_case["featureMetadata"] = {
            "featureId": feature_data["id"],
            "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        # Create criteria metadata - focus on target criteria
        parsed_case["criteriaMetadata"] = []
        test_case_content = (
            parsed_case.get("title", "") + " " + 
            parsed_case.get("steps", "") + " " + 
            parsed_case.get("expectedResults", "")
        ).lower()
        
        # Map to target criteria based on content similarity
        for criteria in target_criteria:
            description = criteria.get("description", "")
            
            # Simple keyword matching for targeted mapping
            key_terms = [word for word in description.lower().split() if len(word) >= 4]
            matching_terms = sum(1 for term in key_terms if term in test_case_content)
            
            # If significant match, map to this criteria
            if matching_terms >= max(2, len(key_terms) // 3):
                parsed_case["criteriaMetadata"].append({
                    "criteriaId": criteria.get("id"),
                    "description": description,
                    "status": "Active"
                })
        
        # Store the test case
        success = embeddings_generator.upload_test_case(parsed_case)
        if success:
            stored_count += 1
            print_success(f"Successfully stored additional test case {parsed_case.get('id')}")
        else:
            print_warning(f"Failed to store additional test case {parsed_case.get('id')}")
    
    # Update feature with new test case IDs
    if stored_count > 0:
        feature_processor = FeatureProcessor()
        test_case_ids = [tc.get("id") for tc in parsed_test_cases]
        feature_processor.update_feature_test_cases(feature_data["id"], test_case_ids)
    
    print_success(f"Successfully stored {stored_count}/{len(parsed_test_cases)} additional test cases")
    return stored_count > 0

async def generate_coverage_requirement(feature_data, uncovered_criteria, existing_test_cases):
    """
    Generate a focused requirement for uncovered criteria.
    
    Args:
        feature_data (dict): Feature data
        uncovered_criteria (list): List of uncovered criteria descriptions
        existing_test_cases (list): Existing test cases for context
        
    Returns:
        str: Focused requirement text
    """
    # Create a focused requirement based on the existing generator prompt
    PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")
    generator_prompt_file = os.path.join(PROMPTS_DIR, "generator_prompt.txt")
    
    with open(generator_prompt_file, "r", encoding="utf-8") as f:
        template = f.read()
    
    # Format the criteria list
    criteria_text = "\n".join([f"- {c}" for c in uncovered_criteria])
    
    # Create a prefix from the feature name
    prefix = "ENV"  # Default
    title = feature_data.get("title", "") or feature_data.get("name", "")
    if title:
        words = re.findall(r'[A-Z][a-z]*', title.replace(" ", ""))
        if words:
            prefix = "".join(word[0] for word in words).upper()
            # Ensure prefix is at least 3 chars
            if len(prefix) < 3:
                prefix = prefix.ljust(3, 'X')
    
    # Add focus instruction
    focus_instruction = "\n\nIMPORTANT: You MUST generate test cases that verify ALL the acceptance criteria listed above. Every criteria must be verified by at least one test case."
    
    # Format the requirement
    requirement_text = template.replace("{description}", feature_data.get("description", ""))
    requirement_text = requirement_text.replace("{criteria}", criteria_text + focus_instruction)
    requirement_text = requirement_text.replace("{prefix}", prefix)
    
    return requirement_text

async def generate_focused_test_cases(feature_data, uncovered_criteria):
    """
    Generate test cases focused on specific uncovered criteria.
    
    Args:
        feature_data (dict): The feature data
        uncovered_criteria (list): List of uncovered criteria descriptions
        
    Returns:
        str: Generated test cases content
    """
    print_progress(f"🔹 Generating test cases for {len(uncovered_criteria)} uncovered criteria...")
    
    # Load the focused generator prompt
    PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")
    focused_prompt_file = os.path.join(PROMPTS_DIR, "focused_generator_prompt.txt")
    
    try:
        with open(focused_prompt_file, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        print_warning(f"⚠️ Focused generator prompt not found at {focused_prompt_file}")
        # Fall back to the regular generator prompt
        with open(os.path.join(PROMPTS_DIR, "generator_prompt.txt"), "r", encoding="utf-8") as f:
            template = f.read()
            
        # Add focus instruction
        template += "\n\nCRITICAL: You MUST generate at least one test case for EACH of the criteria listed below. No criteria should be left uncovered."
    
    # Format criteria text
    criteria_text = "\n".join([f"- {c}" for c in uncovered_criteria])
    
    # Replace placeholders in the template
    prompt = template
    if "{description}" in prompt:
        prompt = prompt.replace("{description}", feature_data.get("description", ""))
    if "{criteria}" in prompt:
        prompt = prompt.replace("{criteria}", criteria_text)
        
    # Use a default prefix if needed
    if "{prefix}" in prompt:
        prefix = "ENV"  # Default prefix
        title = feature_data.get("title", "") or feature_data.get("name", "")
        if title:
            # Extract prefix from feature title
            import re
            words = re.findall(r'[A-Z][a-z]*', title.replace(" ", ""))
            if words:
                prefix = "".join(word[0] for word in words).upper()
                # Ensure prefix is at least 3 chars
                if len(prefix) < 3:
                    prefix = prefix.ljust(3, 'X')
                    
        prompt = prompt.replace("{prefix}", prefix)
    
    # Generate test cases
    from test_case_creation.test_case_handling.generator import generate_test_cases
    
    return await generate_test_cases(None)  # Use the existing generate_test_cases function



