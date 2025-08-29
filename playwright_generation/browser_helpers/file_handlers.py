# playwright_generation/browser_helpers/file_handlers.py

import os
import json

def get_output_path(test_case_id, filename, extension, output_dir=None):
    """
    Generate an output file path based on test case ID and filename.
    
    Args:
        test_case_id (str): Test case ID
        filename (str): Base filename
        extension (str): File extension without dot
        output_dir (str, optional): Output directory
        
    Returns:
        str: Full output file path
    """
    # Ensure extension doesn't start with a dot
    extension = extension.lstrip('.')
    
    # Create filename
    if filename:
        full_filename = f"{filename}.{extension}"
    else:
        full_filename = f"{test_case_id}_selectors.{extension}"
    
    # Use output directory if provided, otherwise current directory
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, full_filename)
    else:
        return full_filename

def save_selectors(selector_list, test_case_id, output_dir=None, json_filename=None, text_filename=None):
    """
    Save selectors to JSON and text files.
    
    Args:
        selector_list (list): List of selector dictionaries
        test_case_id (str): Test case ID
        output_dir (str, optional): Output directory
        json_filename (str, optional): Custom JSON filename
        text_filename (str, optional): Custom text filename
        
    Returns:
        dict: Dictionary with paths to created files
    """
    # Generate file paths
    json_path = get_output_path(test_case_id, json_filename, "json", output_dir)
    text_path = get_output_path(test_case_id, text_filename, "txt", output_dir)
    
    # Generate text content
    selector_text = "# CSS selectors detected by browser_use\n\n"
    for selector in selector_list:
        selector_text += f"Action: {selector.get('action', 'unknown')}\n"
        selector_text += f"Element: {selector.get('tag', 'unknown')}\n"
        selector_text += f"Text: {selector.get('text', '')}\n"
        selector_text += f"Selector: {selector.get('selector', '')}\n\n"
    
    # Save files
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(selector_list, f, indent=2)
    
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(selector_text)
    
    return {
        "json_path": json_path,
        "text_path": text_path
    }