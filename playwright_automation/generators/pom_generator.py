"""
Page Object Model generation functions for AI-enhanced Playwright test generation.
"""

import os
import re
from utils import extract_code_blocks, extract_class_name, save_file

def extract_page_objects(chat_history):
    """
    Extract Page Object classes from chat history.
    
    Args:
        chat_history (list): List of chat messages
        
    Returns:
        list: List of Page Object code blocks
    """
    page_objects = []
    
    # Look for the last message from the POM Engineer
    for message in reversed(chat_history):
        if message["role"] == "assistant" and "POM_Engineer" in message.get("name", ""):
            # Extract code blocks
            code_blocks = extract_code_blocks(message["content"], "javascript")
            if code_blocks:
                # Identify page objects (all blocks except the last one, which is typically the test)
                if len(code_blocks) > 1:
                    page_objects = code_blocks[:-1]
                break
    
    # If no page objects found, try to find them in any assistant message
    if not page_objects:
        for message in reversed(chat_history):
            if message["role"] == "assistant":
                code_blocks = extract_code_blocks(message["content"], "javascript")
                if len(code_blocks) > 1:
                    page_objects = code_blocks[:-1]
                    break
    
    return page_objects

def save_page_objects(page_objects, output_dir):
    """
    Save Page Object classes to individual files.
    
    Args:
        page_objects (list): List of Page Object code blocks
        output_dir (str): Directory to save the files
        
    Returns:
        list: List of saved file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = []
    
    for code_block in page_objects:
        # Extract class name
        class_name = extract_class_name(code_block)
        
        if class_name:
            # Save to file
            file_path = os.path.join(output_dir, f"{class_name}.js")
            save_file(file_path, code_block)
            saved_files.append(file_path)
            print(f"✅ Saved page object: {file_path}")
        else:
            # If class name can't be determined, save with generic name
            file_path = os.path.join(output_dir, f"PageObject_{len(saved_files) + 1}.js")
            save_file(file_path, code_block)
            saved_files.append(file_path)
            print(f"✅ Saved page object with generic name: {file_path}")
    
    return saved_files

def analyze_selectors(selectors_data):
    """
    Analyze selectors to identify logical page groups.
    
    Args:
        selectors_data (list): List of selector data
        
    Returns:
        dict: Dictionary of pages with their elements
    """
    pages = {}
    default_page = "MainPage"
    
    # Initialize default page
    if default_page not in pages:
        pages[default_page] = {
            "elements": {},
            "urls": set()
        }
    
    # Analyze selectors to identify potential pages
    for selector in selectors_data:
        # Try to determine page from selector
        page_name = _get_page_name(selector)
        
        # Initialize page if not exists
        if page_name not in pages:
            pages[page_name] = {
                "elements": {},
                "urls": set()
            }
        
        # Add element to page
        element_name = _get_element_name(selector)
        pages[page_name]["elements"][element_name] = {
            "selector": selector.get("selector", ""),
            "action": selector.get("action", ""),
            "tag": selector.get("tag", ""),
            "text": selector.get("text", "")
        }
    
    return pages

def _get_page_name(selector):
    """Determine page name from selector information."""
    # This is a simplified heuristic - would need enhancement for real-world use
    
    # Check text for page indicators
    text = selector.get("text", "").lower()
    
    # Common patterns that indicate specific pages
    if "login" in text:
        return "LoginPage"
    elif "dashboard" in text:
        return "DashboardPage"
    elif "settings" in text:
        return "SettingsPage"
    elif "environment" in text and "create" in text:
        return "EnvironmentCreationPage"
    elif "environment" in text and "list" in text:
        return "EnvironmentListPage"
    elif "environment" in text:
        return "EnvironmentPage"
    elif "user" in text and "management" in text:
        return "UserManagementPage"
    
    # Default to main page
    return "MainPage"

def _get_element_name(selector):
    """Generate meaningful element name from selector information."""
    action = selector.get("action", "").lower()
    tag = selector.get("tag", "element").lower()
    text = selector.get("text", "").lower()
    
    # For input fields
    if tag == "input" or tag == "textarea":
        if "username" in text or "user" in text:
            return "usernameInput"
        elif "password" in text:
            return "passwordInput"
        elif "email" in text:
            return "emailInput"
        elif "search" in text:
            return "searchInput"
        elif "name" in text:
            return "nameInput"
        elif "url" in text:
            return "urlInput"
        elif "input" in text:
            # Try to extract what's being inputted
            match = re.search(r"input\s+(.+?)\s+into", text)
            if match:
                input_value = match.group(1).strip()
                # Clean up and convert to camelCase
                input_value = re.sub(r'[^a-zA-Z0-9]', ' ', input_value)
                words = input_value.split()
                if words:
                    camel_case = words[0].lower() + ''.join(word.capitalize() for word in words[1:])
                    return f"{camel_case}Input"
        return "textInput"
    
    # For buttons
    if tag == "button" or (action == "click" and tag in ["div", "a", "span"]):
        if "login" in text:
            return "loginButton"
        elif "logout" in text:
            return "logoutButton"
        elif "submit" in text:
            return "submitButton"
        elif "cancel" in text:
            return "cancelButton"
        elif "save" in text:
            return "saveButton"
        elif "delete" in text:
            return "deleteButton"
        elif "create" in text:
            return "createButton"
        elif "edit" in text:
            return "editButton"
        elif "close" in text:
            return "closeButton"
        elif "click" in text:
            # Try to extract what's being clicked
            match = re.search(r"click\s+(.+?)(?:\s+button|\s+on|\s+at|$)", text)
            if match:
                button_name = match.group(1).strip()
                # Clean up and convert to camelCase
                button_name = re.sub(r'[^a-zA-Z0-9]', ' ', button_name)
                words = button_name.split()
                if words:
                    camel_case = words[0].lower() + ''.join(word.capitalize() for word in words[1:])
                    return f"{camel_case}Button"
        return "actionButton"
    
    # For select/dropdown
    if tag == "select":
        return "dropdown"
    
    # For checkbox
    if tag == "checkbox" or (tag == "input" and "checkbox" in text):
        return "checkbox"
    
    # For radio buttons
    if tag == "radio" or (tag == "input" and "radio" in text):
        return "radioButton"
    
    # Generic fallbacks based on tag and action
    if action == "click":
        return f"{tag}Button"
    elif action == "input":
        return f"{tag}Input"
    else:
        return f"{tag}Element"