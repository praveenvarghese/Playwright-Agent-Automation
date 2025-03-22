import asyncio
import os
import json
from test_case_generator import generate_test_cases
from vector_retrieval import VectorRetrievalSystem
from generate_embeddings import EmbeddingsGenerator
from datetime import datetime
from token_monitoring import token_monitor

# File paths for saving test cases (for reference only)
RAW_OPENAI_RESPONSE_FILE = "RawOpenAIResponse.txt"
FINAL_TEST_CASES_FILE = "TestCases.txt"
PROCESSED_TEST_CASES_FILE = "ProcessedTestCases.txt"

async def main():
    """
    Enhanced workflow with direct database upload:
    1. Retrieve similar test cases (if any exist)
    2. Generate new test cases with context from similar ones
    3. Save test cases to files for reference
    4. Directly parse and upload test cases to the database without relying on file parsing
    """
    # Initialize the vector retrieval system
    vector_system = VectorRetrievalSystem()
    embeddings_generator = EmbeddingsGenerator()
    
    # Start a new token tracking session
    print("🔹 Starting new token tracking session...")
    
    # Read requirement from the prompt file
    try:
        with open("test-case-generator-prompt.txt", "r", encoding="utf-8") as f:
            requirement_text = f.read()
    except FileNotFoundError as e:
        print(f"Error: Prompt file not found - {e}")
        return None
    
    print("🔹 Searching for similar existing test cases... Please wait.")
    # Try to retrieve similar test cases based on the requirement
    similar_cases = await vector_system.retrieve_similar_test_cases(requirement_text)
    
    if similar_cases and len(similar_cases) > 0:
        print(f"🔹 Found {len(similar_cases)} similar test cases to use as reference.")
        # Print the titles of similar test cases for reference
        for i, case in enumerate(similar_cases):
            print(f"  {i+1}. {case.get('title', 'Unknown')}")
    else:
        print("🔹 No similar test cases found in the database.")
    
    # Generate test cases with context from similar cases
    print("🔹 Generating test cases with context from similar cases... Please wait.")
    test_cases_content = await generate_test_cases(similar_cases)
    
    # Save OpenAI response to files for reference
    if test_cases_content:
        print(f"🔹 Saving generated test cases to reference files")
        
        # Save raw response
        with open(RAW_OPENAI_RESPONSE_FILE, "w", encoding="utf-8") as f:
            f.write(test_cases_content)
        
        # Save to TestCases.txt - this is also done by generate_test_cases() function
        if not os.path.exists(FINAL_TEST_CASES_FILE):
            with open(FINAL_TEST_CASES_FILE, "w", encoding="utf-8") as f:
                f.write(test_cases_content)
        
        # Store test cases directly in the vector database
        print("🔹 Directly parsing and uploading test cases to database... Please wait.")
        
        # Split the content into individual test cases
        test_case_sections = []
        lines = test_cases_content.split('\n')
        current_section = ""
        
        # Identify test case sections in the content
        for i, line in enumerate(lines):
            if ("Test Case ID:" in line or "ID: TC-ENV" in line) and current_section:
                # Found a new test case, save the previous one
                test_case_sections.append(current_section)
                current_section = line + "\n"
            else:
                current_section += line + "\n"
        
        # Add the last section
        if current_section:
            test_case_sections.append(current_section)
        
        print(f"🔹 Found {len(test_case_sections)} test cases in the generated content")
        
        # Process and upload each test case
        stored_count = 0
        processed_test_cases = []
        
        for i, test_case_text in enumerate(test_case_sections):
            if test_case_text.strip():
                print(f"Processing test case {i+1}...")
                
                # Debug information
                preview = test_case_text.strip()[:100].replace('\n', ' ')
                print(f"  Preview: {preview}...")
                
                # Parse the test case
                parsed_case = embeddings_generator.parse_test_case_from_text(test_case_text)
                
                if parsed_case.get("id"):
                    print(f"  Parsed ID: {parsed_case.get('id')}")
                    print(f"  Title: {parsed_case.get('title')}")
                    
                    # Upload to database
                    success = embeddings_generator.upload_test_case(parsed_case)
                    if success:
                        stored_count += 1
                        processed_test_cases.append(parsed_case)
                        print(f"  Successfully uploaded test case {i+1}")
                    else:
                        print(f"  Failed to upload test case {i+1}")
                else:
                    print(f"  Failed to parse a valid ID for test case {i+1}")
        
        print(f"🔹 Successfully stored {stored_count} test cases in the vector database.")
        
        # Log the processed test cases to a separate file
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        log_file = f"test_cases_log_{timestamp}.txt"
        print(f"🔹 Saving processed test cases details to {log_file}")
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"PROCESSED TEST CASES - {datetime.now().isoformat()}\n\n")
            for i, case in enumerate(processed_test_cases):
                f.write(f"Test Case {i+1}:\n")
                f.write(f"ID: {case.get('id', 'Unknown')}\n")
                f.write(f"Title: {case.get('title', 'Unknown')}\n")
                f.write(f"Steps:\n{case.get('steps', 'None')}\n")
                f.write(f"Expected Results:\n{case.get('expectedResults', 'None')}\n")
                f.write("\n---\n\n")
        
        # Generate and save cost report
        cost_report = token_monitor.get_usage_report()
        cost_report_file = f"token_usage_report_{timestamp}.json"
        print(f"🔹 Saving token usage report to {cost_report_file}")
        
        with open(cost_report_file, "w", encoding="utf-8") as f:
            json.dump(cost_report, f, indent=2)
        
        # Print token usage report
        token_monitor.print_usage_report()

    print("Workflow completed successfully!")

# Run the workflow
if __name__ == "__main__":
    asyncio.run(main())