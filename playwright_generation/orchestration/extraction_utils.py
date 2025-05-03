"""
Extraction utilities for Playwright test generation.
This module provides functions to extract page objects and test scripts
from different response formats.
"""

import re
from playwright_generation.common.utils import extract_code_blocks

def extract_page_objects_from_coordinator(chat_history):
    """
    Extract page objects from coordinator's response in chat history.
    
    Args:
        chat_history (list): Chat history containing messages
            
    Returns:
        list: Extracted page objects
    """
    page_objects = []
    
    # Look through all messages
    for message in chat_history:
        if message["role"] == "assistant":
            content = message["content"]
            
            # Try to extract code blocks
            code_blocks = extract_code_blocks(content, "javascript")
            
            for block in code_blocks:
                # Check if it contains class definitions
                if "class " in block and ("module.exports = " in block):
                    page_objects.append(block)
    
    # Print debugging info
    print(f"Debug: Found {len(page_objects)} potential page objects in the chat history")
    
    return page_objects

def extract_test_script_from_chat(chat_history):
    """
    Extract test script from chat history.
    
    Args:
        chat_history (list): Chat history containing messages
            
    Returns:
        str: Extracted test script or None if not found
    """
    # Look through all messages
    for message in chat_history:
        if message["role"] == "assistant":
            content = message["content"]
            
            # Try to extract code blocks
            code_blocks = extract_code_blocks(content, "javascript")
            
            # Find any block with test function
            for block in code_blocks:
                if "test(" in block and "async" in block:
                    print(f"Debug: Found test script with length {len(block)}")
                    return block
    
    # If no specific test script found, print a debug message
    print("Debug: No test script found in the chat history")
    return None

def extract_page_objects_from_specialized(response):
    """
    Extract page objects from structured response with headers.
    
    Args:
        response (str): Response text with structured headers
            
    Returns:
        list: Extracted page objects
    """
    page_objects = []
    
    # Find sections with file headers and code blocks
    matches = re.findall(r'###\s+\d+\.\s+(\w+\.js).*?```javascript\s+(.*?)```', response, re.DOTALL)
    
    for filename, code_block in matches:
        if "test" not in filename.lower():  # Skip test scripts
            page_objects.append(code_block.strip())
            print(f"Debug: Extracted {filename}")
    
    print(f"Debug: Found {len(page_objects)} potential page objects in the response")
    
    return page_objects

def extract_test_script_from_specialized(response):
    """
    Extract test script from structured response with headers.
    
    Args:
        response (str): Response text with structured headers
            
    Returns:
        str: Extracted test script or None if not found
    """
    # Look for test script with header
    matches = re.findall(r'###\s+\w+\.\s+testCase\.js.*?```javascript\s+(.*?)```', response, re.DOTALL)
    
    if matches and len(matches) > 0:
        test_script = matches[0].strip()
        print(f"Debug: Found test script with length {len(test_script)}")
        return test_script
    
    # Alternative pattern - look for any script with test function
    test_blocks = re.findall(r'```javascript\s+(.*?test\(.*?}\);.*?)```', response, re.DOTALL)
    
    if test_blocks and len(test_blocks) > 0:
        test_script = test_blocks[0].strip()
        print(f"Debug: Found test script with alternative pattern, length {len(test_script)}")
        return test_script
    
    print("Debug: No test script found in the response")
    return None