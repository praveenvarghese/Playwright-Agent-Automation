"""
Extraction utilities for Playwright test generation.
"""

import re
import os
import json

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

def extract_page_objects_from_specialized(response):
    """Extract page objects from structured response with headers."""
    page_objects = []
    
    matches = re.findall(r'###\s+\d+\.\s+(\w+\.js).*?```javascript\s+(.*?)```', response, re.DOTALL)
    
    for filename, code_block in matches:
        if "test" not in filename.lower():
            page_objects.append(code_block.strip())
    
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