"""
Utility functions for AI-enhanced Playwright test generation.
"""

import os
import re
import json
from datetime import datetime

def extract_code_blocks(text, language="javascript"):
    """
    Extract code blocks from text.
    
    Args:
        text (str): Text containing code blocks
        language (str): Language of code blocks to extract
        
    Returns:
        list: List of extracted code blocks
    """
    # Pattern for code blocks with or without language specification
    patterns = [
        rf"```{language}\n(.*?)```",  # With language
        r"```\n(.*?)```"               # Without language
    ]
    
    code_blocks = []
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        code_blocks.extend(matches)
    
    return [block.strip() for block in code_blocks]

def save_file(file_path, content):
    """
    Save content to a file.
    
    Args:
        file_path (str): Path to save the file
        content (str): Content to save
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def create_backup(file_path):
    """
    Create a backup of a file if it exists.
    
    Args:
        file_path (str): Path to the file to backup
        
    Returns:
        str: Path to the backup file or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
        
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_dir = os.path.join(os.path.dirname(file_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    file_name = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, f"{file_name}.{timestamp}.bak")
    
    with open(file_path, "r", encoding="utf-8") as src:
        content = src.read()
        
    with open(backup_path, "w", encoding="utf-8") as dst:
        dst.write(content)
        
    return backup_path

def extract_class_name(code_block):
    """
    Extract class name from a code block.
    
    Args:
        code_block (str): Code block to extract class name from
        
    Returns:
        str: Extracted class name or None if not found
    """
    match = re.search(r"class\s+(\w+)", code_block)
    if match:
        return match.group(1)
    return None

def parse_selectors_file(file_path):
    """
    Parse a selectors JSON file.
    
    Args:
        file_path (str): Path to the selectors file
        
    Returns:
        list: List of selector data or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_test_script(file_path):
    """
    Load a test script from file.
    
    Args:
        file_path (str): Path to the test script
        
    Returns:
        str: Content of the test script or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def create_logger(log_dir="logs"):
    """
    Create a logger for the AI-enhanced generation process.
    
    Args:
        log_dir (str): Directory for log files
        
    Returns:
        function: Logging function
    """
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"generation_{datetime.now().strftime('%Y%m%d%H%M%S')}.log")
    
    def log(message, level="INFO"):
        """Log a message to the log file and console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        
        print(log_message)
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    
    return log

def load_prompt_template(template_path, **kwargs):
    """
    Load a prompt template from a file and format it with variables.
    
    Args:
        template_path (str): Path to the template file
        **kwargs: Variables to use in formatting
        
    Returns:
        str: Formatted prompt
    """
    with open(template_path, 'r', encoding='utf-8') as file:
        template = file.read()
    
    # Format the template with provided variables
    return template.format(**kwargs)
