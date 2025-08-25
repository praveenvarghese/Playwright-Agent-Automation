"""
Extraction utilities for Playwright test generation.
"""

import re
import os
import json
from typing import Dict, List, Set

def extract_code_blocks(text, language="javascript"):
    """Extract code blocks from text."""
    patterns = [
        rf"```{language}\n(.*?)```",
        r"```\n(.*?)```"
    ]
    
    code_blocks = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        code_blocks.extend(matches)
    
    return [block.strip() for block in code_blocks]


"""
Minimal changes needed in orchestration/extraction_utils.py
Just update these two functions:
"""

import re
import os
import json
from typing import Dict, List, Set

def extract_page_objects_from_specialized(response):
    """Extract page objects from JSON format response."""
    page_objects = []
    
    # Try JSON with markdown blocks first
    json_pattern = r'```json\s*(.*?)```'
    json_matches = re.findall(json_pattern, response, re.DOTALL | re.IGNORECASE)
    
    # If no markdown blocks, try parsing the entire response as JSON
    if not json_matches:
        try:
            data = json.loads(response.strip())
            if isinstance(data, dict) and 'files' in data:
                for file_info in data['files']:
                    if file_info.get('path', '').startswith('pages/') and file_info.get('content'):
                        page_objects.append(file_info['content'].strip())
                return page_objects
        except json.JSONDecodeError:
            pass
    
    # Process markdown-wrapped JSON
    for json_text in json_matches:
        try:
            data = json.loads(json_text.strip())
            if isinstance(data, dict) and 'files' in data:
                for file_info in data['files']:
                    if file_info.get('path', '').startswith('pages/') and file_info.get('content'):
                        page_objects.append(file_info['content'].strip())
                break
        except json.JSONDecodeError:
            continue
    
    return page_objects

def extract_test_script_from_specialized(response):
    """Extract test script from structured response with headers."""
    matches = re.findall(r'###\s+\d+\.\s+testCase\.spec\.js.*?```javascript\s+(.*?)```', response, re.DOTALL)
    
    if matches:
        return matches[0].strip()
    
    return None

def load_mcp_execution_log(test_case_id):
    """Load MCP execution log if it exists"""
    mcp_file = f"{test_case_id}_mcp_execution_log.json"
    if os.path.exists(mcp_file):
        with open(mcp_file, 'r') as f:
            return json.load(f)
    return []

def extract_pom_methods(pom_content: str) -> Dict[str, List[str]]:
    """Extract method names from POM classes"""
    methods_by_class = {}
    
    # Find all class definitions
    class_matches = re.findall(r'export class (\w+)', pom_content)
    
    for class_name in class_matches:
        # Extract methods for this class
        class_pattern = rf'export class {class_name}.*?(?=export class|\Z)'
        class_content = re.search(class_pattern, pom_content, re.DOTALL)
        
        if class_content:
            # Find async method definitions
            method_matches = re.findall(r'async (\w+)\s*\(', class_content.group(0))
            methods_by_class[class_name] = method_matches
    
    return methods_by_class

def extract_test_method_calls(test_content: str) -> Dict[str, List[str]]:
    """Extract method calls from test files"""
    calls_by_object = {}
    
    # Find POM instantiations
    instantiation_matches = re.findall(r'const (\w+) = new (\w+)\(', test_content)
    
    for var_name, class_name in instantiation_matches:
        # Find method calls on this object
        call_pattern = rf'{var_name}\.(\w+)\s*\('
        method_calls = re.findall(call_pattern, test_content)
        calls_by_object[class_name] = method_calls
    
    return calls_by_object

def validate_method_consistency(pom_methods: Dict[str, List[str]], 
                              test_calls: Dict[str, List[str]]) -> List[str]:
    """Validate that test calls match POM methods"""
    issues = []
    
    for class_name, called_methods in test_calls.items():
        available_methods = pom_methods.get(class_name, [])
        
        for called_method in called_methods:
            if called_method not in available_methods:
                issues.append(
                    f"❌ {class_name}.{called_method}() called in test but not defined in POM. "
                    f"Available methods: {', '.join(available_methods)}"
                )
    
    return issues

def create_method_validation_prompt(pom_content: str) -> str:
    """Create a validation prompt with extracted method names"""
    methods_by_class = extract_pom_methods(pom_content)
    
    validation_text = "AVAILABLE POM METHODS (use ONLY these):\n"
    for class_name, methods in methods_by_class.items():
        validation_text += f"\n{class_name}:\n"
        for method in methods:
            validation_text += f"  - {method}()\n"
    
    validation_text += "\n⚠️ CRITICAL: Only call methods listed above. Do not invent new method names."
    
    return validation_text