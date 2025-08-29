import json
from datetime import datetime, timezone
import re


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
    # Extract JSON from text
    import re
    import json
    from datetime import datetime, timezone
    
    # Try to find JSON array in the text
    json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', llm_output)
    if json_match:
        json_text = json_match.group(1)
    else:
        # Try to find any JSON array
        json_match = re.search(r'\[\s*\{\s*"(?:id|testCaseId)"[\s\S]*?\}\s*\]', llm_output)
        if json_match:
            json_text = json_match.group(0)
        else:
            print("No JSON found in the output")
            return []
    
    try:
        # Parse the JSON
        parsed_json = json.loads(json_text)
        
        # Process test cases
        processed_cases = []
        for tc in parsed_json:
            processed_tc = {
                # Map field names, supporting both formats
                "id": tc.get("id", tc.get("testCaseId", "")),
                "title": tc.get("title", tc.get("testCaseTitle", "")),
                "steps": format_steps(tc.get("steps", tc.get("testSteps", ""))),
                "expectedResults": tc.get("expectedResults", tc.get("expected_results", 
                                       tc.get("expectedResult", ""))),
                "createdDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "Active",
                "version": "1.0"
            }
            
            # Only include valid test cases
            if processed_tc["id"] and processed_tc["title"] and processed_tc["steps"] and processed_tc["expectedResults"]:
                processed_cases.append(processed_tc)
            else:
                print(f"Skipping test case with ID {processed_tc['id']} - missing required fields")
                
        return processed_cases
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        return []

def format_steps(steps):
    """Format steps consistently regardless of input format."""
    if isinstance(steps, list):
        return "\n".join(steps)
    return steps

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



   