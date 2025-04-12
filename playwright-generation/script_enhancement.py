"""
Test script enhancement functions for AI-enhanced Playwright test generation.
"""

import os
import re
from .utils import extract_code_blocks, save_file

def extract_enhanced_script(chat_history):
    """
    Extract enhanced test script from chat history.
    
    Args:
        chat_history (list): List of chat messages
        
    Returns:
        str: Enhanced test script or None if not found
    """
    # Look for the last message from the Script Engineer
    for message in reversed(chat_history):
        if message["role"] == "assistant" and "Script_Engineer" in message.get("name", ""):
            # Extract code blocks
            code_blocks = extract_code_blocks(message["content"], "javascript")
            if code_blocks and len(code_blocks) > 0:
                # Return the last code block
                return code_blocks[-1]
    
    # If no script found from Script Engineer, try to find in any assistant message
    for message in reversed(chat_history):
        if message["role"] == "assistant":
            code_blocks = extract_code_blocks(message["content"], "javascript")
            if code_blocks and len(code_blocks) > 0:
                return code_blocks[-1]
    
    return None

def analyze_test_script(test_script):
    """
    Analyze test script to identify areas for improvement.
    
    Args:
        test_script (str): Test script to analyze
        
    Returns:
        dict: Analysis results
    """
    analysis = {
        "has_wait_strategies": False,
        "has_assertions": False,
        "has_error_handling": False,
        "has_documentation": False,
        "improvement_areas": []
    }
    
    # Check for wait strategies
    wait_patterns = [
        r"waitFor",
        r"waitForSelector",
        r"waitForLoadState",
        r"waitForNavigation",
        r"waitForTimeout"
    ]
    for pattern in wait_patterns:
        if re.search(pattern, test_script):
            analysis["has_wait_strategies"] = True
            break
    
    # Check for assertions
    assertion_patterns = [
        r"expect\(",
        r"toEqual",
        r"toBe",
        r"toContain",
        r"toHaveText",
        r"toBeVisible"
    ]
    for pattern in assertion_patterns:
        if re.search(pattern, test_script):
            analysis["has_assertions"] = True
            break
    
    # Check for error handling
    error_patterns = [
        r"try\s*{",
        r"catch\s*\(",
        r"finally\s*{"
    ]
    for pattern in error_patterns:
        if re.search(pattern, test_script):
            analysis["has_error_handling"] = True
            break
    
    # Check for documentation
    doc_patterns = [
        r"\/\*\*",
        r"\*\/",
        r"\/\/\s*\w+"
    ]
    doc_count = 0
    for pattern in doc_patterns:
        doc_count += len(re.findall(pattern, test_script))
    
    analysis["has_documentation"] = doc_count > 3  # Arbitrary threshold
    
    # Identify improvement areas
    if not analysis["has_wait_strategies"]:
        analysis["improvement_areas"].append("Add proper wait strategies for better reliability")
    
    if not analysis["has_assertions"]:
        analysis["improvement_areas"].append("Add assertions to verify expected behavior")
    
    if not analysis["has_error_handling"]:
        analysis["improvement_areas"].append("Add error handling for robustness")
    
    if not analysis["has_documentation"]:
        analysis["improvement_areas"].append("Improve documentation and comments")
    
    # Check for hardcoded waits
    if re.search(r"setTimeout|page\.waitForTimeout\(\d+\)", test_script):
        analysis["improvement_areas"].append("Replace hardcoded waits with explicit wait conditions")
    
    return analysis

def save_enhanced_script(test_script, file_path):
    """
    Save enhanced test script to file.
    
    Args:
        test_script (str): Enhanced test script
        file_path (str): Path to save the script
        
    Returns:
        str: Path to the saved script
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Save the script
    save_file(file_path, test_script)
    
    return file_path

def generate_test_variations(test_script, variations_count=2):
    """
    Generate variations of a test script to cover edge cases.
    Not directly used by the agents, but can be a standalone utility.
    
    Args:
        test_script (str): Original test script
        variations_count (int): Number of variations to generate
        
    Returns:
        list: List of test script variations
    """
    # This would typically be handled by the Test Designer Agent
    # For demonstration, we return the original script
    return [test_script]