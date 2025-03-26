"""
Script manager for handling file operations and script versioning.
This module handles saving, updating, and tracking test scripts.
"""

import os
import json
import hashlib
from datetime import datetime

from .utils import format_console_output


def get_test_script_path(test_case_id):
    """
    Get the path where a test script should be saved.
    
    Args:
        test_case_id (str): The test case ID
        
    Returns:
        str: The file path
    """
    # Extract the feature code from the test case ID
    # Example: TC-ENV-001 -> ENV
    parts = test_case_id.split('-')
    if len(parts) >= 2:
        feature_code = parts[1].lower()
    else:
        feature_code = "unknown"
    
    # Create directory path
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                               "..", "playwright_tests", "tests", feature_code))
    
    # Create directory if it doesn't exist
    os.makedirs(tests_dir, exist_ok=True)
    
    # File path
    file_name = f"{test_case_id.lower()}.spec.js"
    return os.path.join(tests_dir, file_name)


def check_script_update_needed(test_case):
    """
    Check if a script needs to be updated based on test case content.
    
    Args:
        test_case (dict): The test case data
        
    Returns:
        bool: True if update is needed, False otherwise
    """
    test_case_id = test_case.get('id', 'unknown')
    script_path = get_test_script_path(test_case_id)
    
    # If script doesn't exist, update is needed
    if not os.path.exists(script_path):
        return True
    
    # Get the script metadata file path
    metadata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                  "..", "playwright_tests", "metadata"))
    os.makedirs(metadata_dir, exist_ok=True)
    
    metadata_file = os.path.join(metadata_dir, f"{test_case_id.lower()}.json")
    
    # If metadata doesn't exist, update is needed
    if not os.path.exists(metadata_file):
        return True
    
    # Load metadata
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except:
        # If metadata can't be loaded, update is needed
        return True
    
    # Calculate hash of current test case
    current_hash = _calculate_test_case_hash(test_case)
    
    # Compare with saved hash
    if metadata.get("test_case_hash") != current_hash:
        return True
    
    # No update needed
    return False


def save_script(test_case, script_content):
    """
    Save a generated test script to file.
    
    Args:
        test_case (dict): The test case data
        script_content (str): The script content
        
    Returns:
        str: The path to the saved script, or None if failed
    """
    test_case_id = test_case.get('id', 'unknown')
    script_path = get_test_script_path(test_case_id)
    
    try:
        # Save the script
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        
        # Calculate hash of test case
        test_case_hash = _calculate_test_case_hash(test_case)
        
        # Save metadata
        _save_script_metadata(test_case, test_case_hash, script_path)
        
        return script_path
    except Exception as e:
        print(format_console_output("error", f"Error saving script: {str(e)}"))
        return None


def _save_script_metadata(test_case, test_case_hash, script_path):
    """
    Save metadata about a generated script.
    
    Args:
        test_case (dict): The test case data
        test_case_hash (str): Hash of test case content
        script_path (str): Path to the saved script
    """
    # Create metadata directory
    metadata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                 "..", "playwright_tests", "metadata"))
    os.makedirs(metadata_dir, exist_ok=True)
    
    # Metadata file path
    test_case_id = test_case.get('id', 'unknown')
    metadata_file = os.path.join(metadata_dir, f"{test_case_id.lower()}.json")
    
    # Metadata content
    metadata = {
        "test_case_id": test_case_id,
        "test_case_title": test_case.get('title', 'Unknown'),
        "test_case_hash": test_case_hash,
        "script_path": script_path,
        "generated_at": datetime.now().isoformat(),
        "feature_id": None
    }
    
    # Add feature_id if available
    if test_case.get("featureMetadata") and test_case["featureMetadata"].get("featureId"):
        metadata["feature_id"] = test_case["featureMetadata"]["featureId"]
    
    # Save metadata
    try:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        print(format_console_output("warning", f"Error saving script metadata: {str(e)}"))


def backup_existing_script(script_path):
    """
    Create a backup of an existing script before overwriting it.
    
    Args:
        script_path (str): Path to the script
        
    Returns:
        str: Path to the backup, or None if not created
    """
    if not os.path.exists(script_path):
        return None
    
    try:
        # Create backups directory
        backup_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                   "..", "playwright_tests", "backups"))
        os.makedirs(backup_dir, exist_ok=True)
        
        # Get script filename
        script_filename = os.path.basename(script_path)
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_filename = f"{os.path.splitext(script_filename)[0]}_{timestamp}.js"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy the script
        with open(script_path, "r", encoding="utf-8") as src:
            content = src.read()
            
        with open(backup_path, "w", encoding="utf-8") as dst:
            dst.write(content)
            
        return backup_path
    except Exception as e:
        print(format_console_output("warning", f"Error creating backup: {str(e)}"))
        return None


def get_all_test_scripts():
    """
    Get a list of all generated test scripts.
    
    Returns:
        list: List of script information dictionaries
    """
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                               "..", "playwright_tests", "tests"))
    
    # If tests directory doesn't exist, return empty list
    if not os.path.exists(tests_dir):
        return []
    
    # Find all script files
    scripts = []
    for root, dirs, files in os.walk(tests_dir):
        for file in files:
            if file.endswith(".spec.js"):
                # Get relative path from tests directory
                rel_path = os.path.relpath(os.path.join(root, file), tests_dir)
                
                # Get test case ID from filename
                test_case_id = os.path.splitext(file)[0].upper()
                
                # Add to list
                scripts.append({
                    "id": test_case_id,
                    "path": os.path.join(root, file),
                    "relative_path": rel_path
                })
    
    return scripts


def _calculate_test_case_hash(test_case):
    """
    Calculate a hash of the test case content for change detection.
    
    Args:
        test_case (dict): The test case data
        
    Returns:
        str: Hash of the test case content
    """
    # Extract the content we want to hash
    content_to_hash = f"{test_case.get('id', '')}-{test_case.get('title', '')}-{test_case.get('steps', '')}-{test_case.get('expectedResults', '')}"
    
    # Calculate hash
    hash_obj = hashlib.md5(content_to_hash.encode())
    return hash_obj.hexdigest()