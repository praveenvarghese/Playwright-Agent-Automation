# common/mcp_pack.py
import re
import json
from typing import Any, Dict, List, Optional

def build_simple_pack(mcp_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build compact format from any MCP log with verification data extraction"""
    steps = []
    verifications = []
    
    for i, entry in enumerate(mcp_log):
        tool = entry.get("tool", "")
        args = entry.get("args", {}) or {}
        result = entry.get("result", {})
        
        # Extract verification snapshots
        if entry.get("is_verification") and tool == "browser_snapshot":
            verification_data = extract_verification_data(entry, i, mcp_log)
            if verification_data:
                verifications.append(verification_data)
            continue
            
        # Skip other snapshots and empty entries
        if tool.endswith("_snapshot") or not tool or not args:
            continue
            
        result_text = _extract_result_text(result)
        
        # Skip failed actions with improved filtering
        if _is_action_failed(result_text):
            continue
            
        # Build step with available data
        step = {"tool": tool, "args": args}
        
        # Add extracted data if available
        selector = _extract_selector(result_text)
        if selector:
            step["selector"] = selector
            
        url_outcome = _extract_url(result_text)
        if url_outcome:
            step["outcome"] = url_outcome
            
        steps.append(step)
    
    return {
        "steps": steps,
        "verifications": verifications
    }

def extract_verification_data(snapshot_entry: Dict[str, Any], index: int, full_log: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract meaningful verification data from snapshot"""
    
    snapshot_content = _extract_result_text(snapshot_entry.get("result", {}))
    if not snapshot_content:
        return None
    
    # Get context - what actions led to this verification
    preceding_actions = get_preceding_actions(full_log, index)
    
    # Extract key verification elements from snapshot
    verification_elements = extract_verification_elements(snapshot_content)
    
    # Determine verification type based on context
    verification_type = determine_verification_type(preceding_actions, verification_elements)
    
    return {
        "type": verification_type,
        "context_actions": preceding_actions,
        "elements": verification_elements,
        "assertions": generate_assertions(verification_type, verification_elements)
    }

def get_preceding_actions(full_log: List[Dict[str, Any]], snapshot_index: int) -> List[Dict[str, Any]]:
    """Get the 1-3 actions that led to this verification point"""
    actions = []
    
    # Look back for recent non-snapshot actions
    for i in range(snapshot_index - 1, max(snapshot_index - 4, -1), -1):
        entry = full_log[i]
        if not entry.get("tool", "").endswith("_snapshot"):
            actions.insert(0, {
                "tool": entry.get("tool"),
                "element": entry.get("args", {}).get("element"),
                "text": entry.get("args", {}).get("text")
            })
    
    return actions

def extract_verification_elements(snapshot_content: str) -> Dict[str, Any]:
    """Extract key elements from snapshot content"""
    elements = {}
    
    # Extract URL
    url_match = re.search(r"Page URL:\s*([^\n]+)", snapshot_content)
    if url_match:
        elements["url"] = url_match.group(1).strip()
    
    # Extract visible elements with specific states
    elements["visible_elements"] = []
    elements["active_elements"] = []
    elements["text_content"] = []
    
    # Find active elements
    active_matches = re.findall(r'- (.*?) \[active\]', snapshot_content)
    elements["active_elements"] = active_matches
    
    # Find specific text content
    text_matches = re.findall(r'- (.*?):\s*(.+)', snapshot_content)
    for match in text_matches:
        if "text:" in match[0] or "heading" in match[0]:
            elements["text_content"].append(match[1].strip())
    
    # Find button states
    button_matches = re.findall(r'button "([^"]+)"(?:\s*\[([^\]]+)\])?', snapshot_content)
    elements["buttons"] = [{"text": text, "state": state or "normal"} for text, state in button_matches]
    
    return elements

def determine_verification_type(actions: List[Dict[str, Any]], elements: Dict[str, Any]) -> str:
    """Determine what type of verification this represents"""
    
    if not actions:
        return "page_state"
    
    last_action = actions[-1] if actions else {}
    last_tool = last_action.get("tool", "")
    
    # Navigation verification
    if last_tool == "browser_click" and elements.get("url"):
        return "navigation"
    
    # Login verification  
    if any("Login" in str(action.get("element", "")) for action in actions):
        return "authentication"
    
    # Form submission verification
    if last_tool == "browser_click" and "Save" in str(last_action.get("element", "")):
        return "form_submission"
    
    # Element interaction verification
    if last_tool in ["browser_hover", "browser_click"]:
        return "element_interaction"
    
    return "page_state"

def generate_assertions(verification_type: str, elements: Dict[str, Any]) -> List[str]:
    """Generate Playwright assertion code based on verification type and elements"""
    
    assertions = []
    
    if verification_type == "navigation" and elements.get("url"):
        url = elements["url"]
        # Extract path for URL assertion
        path_match = re.search(r'https?://[^/]+(/.*)', url)
        if path_match:
            path = path_match.group(1)
            assertions.append(f"await expect(this.page).toHaveURL(/{re.escape(path)}$/);")
    
    if verification_type == "authentication":
        # Check for login indicators
        if any("admin" in str(button.get("text", "")).lower() for button in elements.get("buttons", [])):
            assertions.append("await expect(this.page.getByText('admin')).toBeVisible();")
        if elements.get("url") and "applications" in elements["url"]:
            assertions.append("await expect(this.page).toHaveURL(/\\/applications$/);")
    
    if verification_type == "element_interaction":
        # Check for active elements
        for active_el in elements.get("active_elements", []):
            if "Users" in active_el:
                assertions.append("await expect(this.page.getByRole('link', { name: 'Users' })).toHaveAttribute('active', '');")
    
    if verification_type == "form_submission":
        # Generic form submission verification
        assertions.append("await expect(this.page.locator('[data-testid=\"success-indicator\"]')).toBeVisible();")
    
    # Always add a page stability check
    assertions.append("await expect(this.page).not.toHaveURL(/error/);")
    
    return assertions

def _is_action_failed(result_text: str) -> bool:
    """Check if the Playwright action itself failed (improved version)"""
    if not result_text:
        return False
    
    # Only filter out if the Playwright action failed, not console errors
    action_failure_indicators = [
        "Error:", "TimeoutError", "locator.click: Error", 
        "locator.fill: Error", "locator.hover: Error",
        "Navigation timeout", "Target closed", "Ref.*not found"
    ]
    
    # Don't filter console errors - they don't mean the action failed
    console_error_patterns = [
        "### New console messages",
        "[ERROR] Failed to load resource",
        "console.error"
    ]
    
    # If it's just console errors, don't skip
    if any(pattern in result_text for pattern in console_error_patterns):
        # Check if there's also an actual Playwright action failure
        return any(indicator in result_text for indicator in action_failure_indicators)
    
    # Check for actual action failures
    return any(indicator in result_text for indicator in action_failure_indicators)

def _extract_result_text(result: Dict[str, Any]) -> str:
    """Extract text from result content"""
    try:
        content = result.get("content", [])
        if content and isinstance(content[0], dict):
            return content[0].get("text", "")
    except:
        pass
    return ""

def _extract_selector(result_text: str) -> str:
    """Extract any selector from result text"""
    if not result_text:
        return ""
    
    # Look for any getBy* pattern
    match = re.search(r"getBy\w*\([^)]+\)", result_text)
    return match.group(0) if match else ""

def _extract_url(result_text: str) -> str:
    """Extract any URL from result text"""
    if not result_text:
        return ""
        
    # Look for any URL pattern
    match = re.search(r"(?:Page |Current )?URL:\s*([^\n]+)", result_text)
    return match.group(1).strip() if match else ""

# Testing function
def test_verification_extraction():
    """Test the verification extraction with sample data"""
    
    # Sample verification entry from your log
    sample_verification = {
        "tool": "browser_snapshot",
        "is_verification": True,
        "result": {
            "content": [{
                "text": """### Page state
- Page URL: https://praveen-2.aimms.cloud/applications
- Page Title: AIMMS Cloud Portal
- button "ROOT admin expand_more" [ref=e49]:
  - generic [ref=e50]: ROOT
  - generic [ref=e51]:
    - text: admin
- link "Users" [cursor=pointer]"""
            }]
        }
    }
    
    verification_data = extract_verification_data(sample_verification, 4, [])
    print("Extracted verification data:")
    print(json.dumps(verification_data, indent=2))
    
    return verification_data

if __name__ == "__main__":
    test_verification_extraction()