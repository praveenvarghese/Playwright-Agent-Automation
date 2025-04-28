import os
from datetime import datetime

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

