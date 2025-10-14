"""
File utilities for saving generated code
"""

import os
import re

def save_page_objects(page_objects, output_dir):
    """Save page objects to files - extract class names from content."""
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = []
    for i, code_block in enumerate(page_objects):
        # Extract class name from the actual code content
        match = re.search(r'export class\s+(\w+)', code_block)
        if match:
            filename = f"{match.group(1)}.js"
        else:
            filename = f"PageObject_{i+1}.js"
        
        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code_block)
        
        saved_files.append(file_path)
        print(f"✅ Saved: {file_path}")
    
    return saved_files

def save_test_script(test_content, output_dir, test_case_id):
    """Save test script to file"""
    os.makedirs(output_dir, exist_ok=True)
    
    test_file_path = os.path.join(output_dir, f"{test_case_id}.spec.js")
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"✅ Saved test: {test_file_path}")
    return test_file_path