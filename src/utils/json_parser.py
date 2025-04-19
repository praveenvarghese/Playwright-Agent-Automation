import json
from datetime import datetime, timezone
import re

def update_generator_prompt(original_prompt):
    """
    Enhance the generator prompt to request JSON output without hardcoding structure.
    
    Args:
        original_prompt (str): The original generator prompt
        
    Returns:
        str: Enhanced prompt requesting JSON format
    """
    # Add JSON instruction to the existing prompt without changing its essence
    json_instruction = """
Please provide your response in JSON format for easier processing.
Each test case should be a JSON object with at least id, title, steps, and expectedResults fields.
Include all test cases in a JSON array.
"""
    
    # Combine with original prompt while preserving its content
    enhanced_prompt = original_prompt + "\n\n" + json_instruction
    return enhanced_prompt

def extract_json_from_text(text):
    """
    Extract JSON from text, handling various ways an LLM might format the response.
    
    Args:
        text (str): Text that may contain JSON
        
    Returns:
        str: Extracted JSON string or None if not found
    """
    # Try to find JSON array
    array_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if array_match:
        return array_match.group(0)
    
    # Try to find single JSON object
    object_match = re.search(r'\{\s*".*"\s*:.*\}', text, re.DOTALL)
    if object_match:
        return object_match.group(0)
    
    # Try to find code block that might contain JSON
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if code_block_match:
        return code_block_match.group(1).strip()
    
    return None

def parse_test_cases_from_llm_output(llm_output):
    """
    Parse test cases from LLM output, trying multiple approaches.
    
    Args:
        llm_output (str): Raw output from the LLM
        
    Returns:
        list: List of parsed test case dictionaries
    """
    # First try to extract JSON from the text
    json_text = extract_json_from_text(llm_output)
    
    if json_text:
        try:
            # Try parsing the extracted JSON
            parsed_json = json.loads(json_text)
            
            # Handle both array and single object formats
            if isinstance(parsed_json, dict):
                test_cases = [parsed_json]
            elif isinstance(parsed_json, list):
                test_cases = parsed_json
            else:
                raise ValueError("Unexpected JSON structure")
            
            # Process each test case to ensure consistent structure
            processed_cases = []
            for tc in test_cases:
                # Create a standardized test case with required fields
                processed_tc = {
                    "id": sanitize_id(tc.get("id", "")),
                    "title": tc.get("title", ""),
                    "createdDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "status": "Active",
                    "version": "1.0"
                }
                
                # Handle steps field which could be string or array
                steps = tc.get("steps", "")
                if isinstance(steps, list):
                    processed_tc["steps"] = "\n".join(steps)
                else:
                    processed_tc["steps"] = steps
                
                # Handle expectedResults field which could be string or array
                expected_results = tc.get("expectedResults", "")
                if isinstance(expected_results, list):
                    processed_tc["expectedResults"] = "\n".join(expected_results)
                else:
                    processed_tc["expectedResults"] = expected_results
                
                # Generate ID if missing or invalid
                if not processed_tc["id"]:
                    processed_tc["id"] = f"TC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                processed_cases.append(processed_tc)
            
            return processed_cases
        
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
    
    # If JSON parsing fails, fall back to existing text parsing
    print("Falling back to traditional text parsing")
    return parse_test_cases_from_text(llm_output)

def sanitize_id(id_string):
    """
    Sanitize a test case ID to ensure it only contains valid characters.
    
    Args:
        id_string (str): The original ID
        
    Returns:
        str: Sanitized ID
    """
    if not id_string:
        return ""
    
    # Remove any invalid characters, keeping only alphanumeric, underscore, dash, and equals
    return re.sub(r'[^a-zA-Z0-9_\-=]', '', id_string)

def parse_test_cases_from_text(text):
    """
    Parse test cases using traditional text parsing approach.
    This is a fallback when JSON parsing fails.
    
    Args:
        text (str): Text containing test cases
        
    Returns:
        list: List of parsed test case dictionaries
    """
    # Split into test case sections
    sections = []
    current_section = ""
    
    for line in text.split('\n'):
        # Look for test case headers (flexible matching)
        if re.search(r'(?:Test Case|Case)\s*(?:ID|Id|#)?\s*:?\s*\S+', line) and current_section:
            sections.append(current_section)
            current_section = line + "\n"
        else:
            current_section += line + "\n"
    
    if current_section:
        sections.append(current_section)
    
    # Process each section
    processed_cases = []
    for section in sections:
        if not section.strip():
            continue
        
        tc = {}
        
        # Extract ID
        id_match = re.search(r'(?:Test Case|Case)\s*(?:ID|Id|#)?\s*:?\s*(\S+)', section)
        if id_match:
            tc["id"] = sanitize_id(id_match.group(1))
        else:
            tc["id"] = f"TC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Extract title
        title_match = re.search(r'(?:Title|Name)\s*:?\s*(.+?)(?:\n|$)', section)
        if title_match:
            tc["title"] = title_match.group(1).strip()
        
        # Extract steps
        steps_match = re.search(r'(?:Steps|Test Steps|Procedure)\s*:?\s*([\s\S]*?)(?:Expected Result|Expected)', section)
        if steps_match:
            tc["steps"] = steps_match.group(1).strip()
        
        # Extract expected results
        expected_match = re.search(r'(?:Expected Result|Expected Results)\s*:?\s*([\s\S]*?)(?:\n\s*(?:Test Case|Case|$)|\Z)', section, re.DOTALL)
        if expected_match:
            tc["expectedResults"] = expected_match.group(1).strip()
        
        # Add metadata
        tc["createdDate"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        tc["status"] = "Active"
        tc["version"] = "1.0"
        
        processed_cases.append(tc)
    
    return processed_cases

# Example usage in the main workflow
def enhance_test_case_generation(feature_data):
    """
    Enhance test case generation to use JSON format.
    
    Args:
        feature_data (dict): Feature data
        
    Returns:
        str: Enhanced prompt for test case generation
    """
    # Read the original prompt
    import os
    PROMPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "prompts"))
    generator_prompt_file = os.path.join(PROMPTS_DIR, "generator_prompt.txt")
    
    with open(generator_prompt_file, "r", encoding="utf-8") as f:
        original_prompt = f.read()
    
    # Enhance the prompt to request JSON
    enhanced_prompt = update_generator_prompt(original_prompt)
    
    return enhanced_prompt