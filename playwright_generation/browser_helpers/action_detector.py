# playwright_generation/browser_helpers/action_detector.py

def detect_action_type(content, default="unknown"):
    """
    Detect the action type based on content text.
    
    Args:
        content (str): The content text to analyze
        default (str): Default action type if none detected
        
    Returns:
        str: Detected action type
    """
    # Convert to lowercase for case-insensitive matching
    if not content:
        return default
        
    content = content.lower()
    
    # Define action keywords mapping
    action_keywords = {
        "click": ["click", "press", "tap", "select button"],
        "input": ["input", "type", "enter", "fill"],
        "scroll": ["scroll", "swipe"],
        "select": ["select option", "choose from dropdown"],
        "hover": ["hover", "mouse over"],
        "drag": ["drag", "move element"],
        "upload": ["upload", "attach file"],
        "check": ["check", "uncheck", "toggle"]
    }
    
    # Check for each action type
    for action_type, keywords in action_keywords.items():
        if any(keyword in content for keyword in keywords):
            return action_type
            
    # Return default if no match found
    return default