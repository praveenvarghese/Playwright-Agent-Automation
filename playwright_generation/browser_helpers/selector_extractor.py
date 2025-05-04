# playwright_generation/browser_helpers/selector_extractor.py

from .action_detector import detect_action_type

def extract_selectors_from_browser_result(result, include_duplicates=False):
    """
    Extract selectors from browser_use result.
    
    Args:
        result (dict): Browser automation result
        include_duplicates (bool): Whether to include duplicate selectors
        
    Returns:
        list: List of extracted selectors
    """
    seen = set()
    selector_list = []
    
    # Process history items
    history_items = result.get("history", []) if isinstance(result, dict) else []
    
    for history_item in history_items:
        # Extract actions and elements
        actions = history_item.get("result", []) if isinstance(history_item, dict) else []
        elements = history_item.get("state", {}).get("interacted_element", []) if isinstance(history_item, dict) else []
        
        for action, element in zip(actions, elements):
            # Skip invalid elements
            if not element or not isinstance(element, dict) or "css_selector" not in element:
                continue
                
            # Get selector
            selector = element["css_selector"]
            
            # Skip duplicates if requested
            if not include_duplicates and selector in seen:
                continue
                
            seen.add(selector)
            
            # Get element tag
            tag = element.get("tag_name", "unknown")
            
            # Get content text
            extracted_content = action.get("extracted_content") if isinstance(action, dict) else None
            content = "" if extracted_content is None else str(extracted_content)
            
            # Detect action type
            action_type = detect_action_type(content)
            
            # Add to selector list
            selector_list.append({
                "action": action_type,
                "tag": tag,
                "text": content,
                "selector": selector
            })
    
    return selector_list