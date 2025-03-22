import os
from datetime import datetime

# Import modules using the new structure
from src.test_cases.generator import generate_test_cases
from src.vector_search.retrieval import VectorRetrievalSystem
from src.vector_search.embeddings import EmbeddingsGenerator

# Define constants for all path references
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PROMPTS_DIR = os.path.join(PROJECT_ROOT, "prompts")

# Create necessary directories
for directory in [LOGS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

# Helper functions for message formatting
def print_progress(message): print(f"🔹 {message}")
def print_success(message): print(f"✅ {message}")
def print_warning(message): print(f"⚠️ {message}")
def print_error(message): print(f"❌ {message}")

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

async def process_and_store_test_cases(test_cases_content):
    """Process the generated test cases and store them in the database."""
    print_progress("Processing and uploading test cases...")
    
    # Split the content into individual test cases
    test_case_sections = []
    current_section = ""
    
    for line in test_cases_content.split('\n'):
        if ("Test Case ID:" in line or "ID: TC-ENV" in line) and current_section:
            test_case_sections.append(current_section)
            current_section = line + "\n"
        else:
            current_section += line + "\n"
    
    if current_section:
        test_case_sections.append(current_section)
    
    print_progress(f"Found {len(test_case_sections)} test cases in the generated content")
    
    # Process each test case
    embeddings_generator = EmbeddingsGenerator()
    stored_count = 0
    processed_test_cases = []
    
    for i, test_case_text in enumerate(test_case_sections, 1):  # Start index from 1
        if not test_case_text.strip():
            continue
            
        print(f"Processing test case {i}...")
        parsed_case = embeddings_generator.parse_test_case_from_text(test_case_text)
        
        if parsed_case.get("id"):
            print(f"  ID: {parsed_case.get('id')}")
            print(f"  Title: {parsed_case.get('title', '')}")
            
            success = embeddings_generator.upload_test_case(parsed_case)
            if success:
                stored_count += 1
                processed_test_cases.append(parsed_case)
                print_success(f"  Successfully uploaded test case {i}")
            else:
                print_warning(f"  Failed to upload test case {i}")
        else:
            print_error(f"  Failed to parse a valid ID for test case {i}")
    
    print_success(f"Successfully stored {stored_count} test cases in the vector database.")
    
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
            f.write("\n---\n\n")