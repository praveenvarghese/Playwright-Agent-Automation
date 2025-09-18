# common/mcp_pack.py
import re
from typing import Any, Dict, List, Optional

def build_simple_pack(mcp_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build compact format from any MCP log - works with ANY tool"""
    steps = []
    
    for entry in mcp_log:
        tool = entry.get("tool", "")
        args = entry.get("args", {}) or {}
        result = entry.get("result", {})
        
        # Skip snapshots and empty entries
        if tool.endswith("_snapshot") or not tool or not args:
            continue
            
        result_text = _extract_result_text(result)
        
        # Skip failed actions 
        if "error" in result_text.lower():
            continue
            
        # Build step with ALL available data
        step = {"tool": tool, "args": args}
        
        # Add extracted data if available
        selector = _extract_selector(result_text)
        if selector:
            step["selector"] = selector
            
        url_outcome = _extract_url(result_text)
        if url_outcome:
            step["outcome"] = url_outcome
            
        steps.append(step)
    
    return {"steps": steps}


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
    """Extract any selector from result text - no assumptions"""
    if not result_text:
        return ""
    
    # Look for any getBy* pattern
    match = re.search(r"getBy\w*\([^)]+\)", result_text)
    return match.group(0) if match else ""

def _extract_url(result_text: str) -> str:
    """Extract any URL from result text - no assumptions"""
    if not result_text:
        return ""
        
    # Look for any URL pattern
    match = re.search(r"(?:Page |Current )?URL:\s*([^\n]+)", result_text)
    return match.group(1).strip() if match else ""


# For testing and debugging
def test_compact_format():
    """Test function to verify the compact format works correctly."""
    
    sample_mcp_log = [
    {
        "tool": "browser_navigate",
        "args": {
        "url": "https://praveen-2.aimms.cloud/v3/users/"
        },
        "description": "browser_navigate called with arguments {'url': 'https://praveen-2.aimms.cloud/v3/users/'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.goto('https://praveen-2.aimms.cloud/v3/users/');\n```\n\n### Page state\n- Page URL: https://praveen-2.aimms.cloud/users/\n- Page Title: AIMMS Cloud Portal\n- Page Snapshot:\n```yaml\n- generic [ref=e3]:\n  - banner [ref=e4]:\n    - link \"Loading...\" [ref=e6] [cursor=pointer]:\n      - /url: /\n      - generic [ref=e7]: Loading...\n  - main [ref=e8]\n  - contentinfo [ref=e10]:\n    - generic [ref=e12]:\n      - generic [ref=e13]:\n        - paragraph [ref=e14]: Copyright \u00a9 2010 - 2025 AIMMS B.V.\n        - paragraph [ref=e15]: \"AIMMS Cloud Version: Loading...\"\n      - paragraph [ref=e16]:\n        - text: By using this application you are agreeing to the\n        - link \"Privacy Statement for the Cloud\" [ref=e17] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/cloud/privacy.html\n        - text: and the\n        - link \"Responsible Disclosure Policy\" [ref=e18] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/infosec/responsible-disclosure.html\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_fill_form",
        "args": {
        "fields": [
            {
            "name": "Username",
            "type": "textbox",
            "ref": "e21",
            "value": "admin"
            },
            {
            "name": "Password",
            "type": "textbox",
            "ref": "e26",
            "value": "admin"
            }
        ]
        },
        "description": "browser_fill_form called with arguments {'fields': [{'name': 'Username', 'type': 'textbox', 'ref': 'e21', 'value': 'admin'}, {'name': 'Password', 'type': 'textbox', 'ref': 'e26', 'value': 'admin'}]}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Result\nError: locator.fill: Error: Element is not an <input>, <textarea>, <select> or [contenteditable] and does not have a role allowing [aria-readonly]\nCall log:\n\u001b[2m  - waiting for locator('aria-ref=e21')\u001b[22m\n\u001b[2m    - locator resolved to <fieldset class=\"login-form__fields\">\u2026</fieldset>\u001b[22m\n\u001b[2m    - fill(\"admin\")\u001b[22m\n\u001b[2m  - attempting fill action\u001b[22m\n\u001b[2m    - waiting for element to be visible, enabled and editable\u001b[22m\n\n"
            }
        ]
        }
    },
    {
        "tool": "browser_snapshot",
        "args": {},
        "description": "browser_snapshot called with arguments {}",
        "is_verification": True
    },
    {
        "tool": "browser_type",
        "args": {
        "element": "Username",
        "ref": "e30",
        "text": "admin"
        },
        "description": "browser_type called with arguments {'element': 'Username', 'ref': 'e30', 'text': 'admin'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('textbox', { name: 'Username' }).fill('admin');\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_type",
        "args": {
        "element": "Password",
        "ref": "e35",
        "text": "admin"
        },
        "description": "browser_type called with arguments {'element': 'Password', 'ref': 'e35', 'text': 'admin'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('textbox', { name: 'Password' }).fill('admin');\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_click",
        "args": {
        "element": "Login",
        "ref": "e36"
        },
        "description": "browser_click called with arguments {'element': 'Login', 'ref': 'e36'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('button', { name: 'Login' }).click();\n```\n\n### Page state\n- Page URL: https://praveen-2.aimms.cloud/applications\n- Page Title: AIMMS Cloud Portal\n- Page Snapshot:\n```yaml\n- generic [ref=e2]:\n  - generic [ref=e4] [cursor=pointer]:\n    - generic [ref=e47]:\n      - generic [ref=e7]: error\n      - generic [ref=e8]: The SAML environment 'TestEnvironment' is incorrectly configured. Please contact your administrator.\n    - generic [ref=e9]:\n      - progressbar \"notification timer\"\n  - generic [ref=e48]:\n    - banner [ref=e49]:\n      - generic [ref=e50]:\n        - link \"Logo\" [ref=e51] [cursor=pointer]:\n          - /url: /\n          - img \"Logo\" [ref=e52]\n        - navigation [ref=e53]:\n          - link \"Apps\":\n            - /url: /applications\n          - link \"Sessions\" [ref=e54] [cursor=pointer]:\n            - /url: /sessions\n          - link \"Users\" [ref=e55] [cursor=pointer]:\n            - /url: /users\n          - link \"About\" [ref=e56] [cursor=pointer]:\n            - /url: /about\n        - button \"ROOT admin expand_more\" [ref=e57]:\n          - generic [ref=e58]: ROOT\n          - generic [ref=e59]:\n            - text: admin\n            - generic [ref=e60]: expand_more\n    - main [ref=e61]:\n      - generic [ref=e62]:\n        - generic [ref=e63]:\n          - generic [ref=e67]:\n            - textbox [ref=e68]:\n              - /placeholder: Search apps (0 available)\n            - generic [ref=e69]: search\n          - generic [ref=e70]:\n            - button \"New category\" [ref=e71]:\n              - generic [ref=e72]: New category\n            - button \"New app\" [ref=e73]:\n              - generic [ref=e74]: New app\n        - list [ref=e75]\n    - contentinfo [ref=e76]:\n      - generic [ref=e78]:\n        - generic [ref=e79]:\n          - paragraph [ref=e80]: Copyright \u00a9 2010 - 2025 AIMMS B.V.\n          - paragraph [ref=e81]: \"AIMMS Cloud Version: 25.6.1.0\"\n        - paragraph [ref=e82]:\n          - text: By using this application you are agreeing to the\n          - link \"Privacy Statement for the Cloud\" [ref=e83] [cursor=pointer]:\n            - /url: https://documentation.aimms.com/cloud/privacy.html\n          - text: and the\n          - link \"Responsible Disclosure Policy\" [ref=e84] [cursor=pointer]:\n            - /url: https://documentation.aimms.com/infosec/responsible-disclosure.html\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_snapshot",
        "args": {},
        "description": "browser_snapshot called with arguments {}",
        "is_verification": True
    },
    {
        "tool": "browser_click",
        "args": {
        "element": "Users Tab",
        "ref": "e55"
        },
        "description": "browser_click called with arguments {'element': 'Users Tab', 'ref': 'e55'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('link', { name: 'Users' }).click();\n```\n\n### Page state\n- Page URL: https://praveen-2.aimms.cloud/users\n- Page Title: AIMMS Cloud Portal\n- Page Snapshot:\n```yaml\n- generic [ref=e48]:\n  - banner [ref=e49]:\n    - generic [ref=e50]:\n      - link \"Logo\" [ref=e51] [cursor=pointer]:\n        - /url: /\n        - img \"Logo\" [ref=e52]\n      - navigation [ref=e53]:\n        - link \"Apps\" [ref=e85] [cursor=pointer]:\n          - /url: /applications\n        - link \"Sessions\" [ref=e54] [cursor=pointer]:\n          - /url: /sessions\n        - link \"Users\" [active]:\n          - /url: /users\n        - link \"About\" [ref=e56] [cursor=pointer]:\n          - /url: /about\n      - button \"ROOT admin expand_more\" [ref=e57]:\n        - generic [ref=e58]: ROOT\n        - generic [ref=e59]:\n          - text: admin\n          - generic [ref=e60]: expand_more\n  - main [ref=e61]:\n    - generic [ref=e86]:\n      - generic [ref=e87]:\n        - generic [ref=e88]:\n          - article [ref=e89]:\n            - heading \"ROOT Root Environment\" [level=1] [ref=e90]:\n              - text: ROOT\n              - generic [ref=e91]: Root Environment\n            - list [ref=e92]:\n              - listitem [ref=e93]: Native\n          - article [ref=e94]:\n            - heading \"TestEnvironment\" [level=1] [ref=e95]\n            - list [ref=e96]:\n              - listitem [ref=e97]: Linked\n        - button \"add Create environment\" [ref=e98]:\n          - generic [ref=e99]: add\n          - generic [ref=e100]: Create environment\n      - generic [ref=e102]:\n        - navigation [ref=e103]:\n          - tablist [ref=e104]:\n            - listitem [ref=e105]:\n              - tab \"Groups (0)\" [selected] [ref=e106]:\n                - generic [ref=e107]: Groups\n                - generic [ref=e108]: (0)\n            - listitem [ref=e109]:\n              - tab \"Users (0)\" [ref=e110]:\n                - generic [ref=e111]: Users\n                - generic [ref=e112]: (0)\n        - generic:\n          - tabpanel \"Groups (0)\"\n  - contentinfo [ref=e76]:\n    - generic [ref=e78]:\n      - generic [ref=e79]:\n        - paragraph [ref=e80]: Copyright \u00a9 2010 - 2025 AIMMS B.V.\n        - paragraph [ref=e81]: \"AIMMS Cloud Version: 25.6.1.0\"\n      - paragraph [ref=e82]:\n        - text: By using this application you are agreeing to the\n        - link \"Privacy Statement for the Cloud\" [ref=e83] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/cloud/privacy.html\n        - text: and the\n        - link \"Responsible Disclosure Policy\" [ref=e84] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/infosec/responsible-disclosure.html\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_hover",
        "args": {
        "element": "TestEnvironment",
        "ref": "e95"
        },
        "description": "browser_hover called with arguments {'element': 'TestEnvironment', 'ref': 'e95'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('heading', { name: 'TestEnvironment' }).hover();\n```\n\n### Page state\n- Page URL: https://praveen-2.aimms.cloud/users\n- Page Title: AIMMS Cloud Portal\n- Page Snapshot:\n```yaml\n- generic [ref=e48]:\n  - banner [ref=e49]:\n    - generic [ref=e50]:\n      - link \"Logo\" [ref=e51] [cursor=pointer]:\n        - /url: /\n        - img \"Logo\" [ref=e52]\n      - navigation [ref=e53]:\n        - link \"Apps\" [ref=e85] [cursor=pointer]:\n          - /url: /applications\n        - link \"Sessions\" [ref=e54] [cursor=pointer]:\n          - /url: /sessions\n        - link \"Users\" [active]:\n          - /url: /users\n        - link \"About\" [ref=e56] [cursor=pointer]:\n          - /url: /about\n      - button \"ROOT admin expand_more\" [ref=e57]:\n        - generic [ref=e58]: ROOT\n        - generic [ref=e59]:\n          - text: admin\n          - generic [ref=e60]: expand_more\n  - main [ref=e61]:\n    - generic [ref=e86]:\n      - generic [ref=e87]:\n        - generic [ref=e88]:\n          - article [ref=e89]:\n            - heading \"ROOT Root Environment\" [level=1] [ref=e90]:\n              - text: ROOT\n              - generic [ref=e91]: Root Environment\n            - list [ref=e92]:\n              - listitem [ref=e93]: Native\n          - article [ref=e94] [cursor=pointer]:\n            - heading \"TestEnvironment\" [level=1] [ref=e95]\n            - list [ref=e96]:\n              - listitem [ref=e97]: Linked\n            - button \"more_vert\" [ref=e113]:\n              - generic [ref=e114]: more_vert\n        - button \"add Create environment\" [ref=e98]:\n          - generic [ref=e99]: add\n          - generic [ref=e100]: Create environment\n      - generic [ref=e102]:\n        - navigation [ref=e103]:\n          - tablist [ref=e104]:\n            - listitem [ref=e105]:\n              - tab \"Groups (0)\" [selected] [ref=e106]:\n                - generic [ref=e107]: Groups\n                - generic [ref=e108]: (0)\n            - listitem [ref=e109]:\n              - tab \"Users (0)\" [ref=e110]:\n                - generic [ref=e111]: Users\n                - generic [ref=e112]: (0)\n        - generic:\n          - tabpanel \"Groups (0)\"\n  - contentinfo [ref=e76]:\n    - generic [ref=e78]:\n      - generic [ref=e79]:\n        - paragraph [ref=e80]: Copyright \u00a9 2010 - 2025 AIMMS B.V.\n        - paragraph [ref=e81]: \"AIMMS Cloud Version: 25.6.1.0\"\n      - paragraph [ref=e82]:\n        - text: By using this application you are agreeing to the\n        - link \"Privacy Statement for the Cloud\" [ref=e83] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/cloud/privacy.html\n        - text: and the\n        - link \"Responsible Disclosure Policy\" [ref=e84] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/infosec/responsible-disclosure.html\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_click",
        "args": {
        "element": "three dots",
        "ref": "e113"
        },
        "description": "browser_click called with arguments {'element': 'three dots', 'ref': 'e113'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('button', { name: 'more_vert' }).click();\n```\n\n### Page state\n- Page URL: https://praveen-2.aimms.cloud/users\n- Page Title: AIMMS Cloud Portal\n- Page Snapshot:\n```yaml\n- generic [ref=e48]:\n  - banner [ref=e49]:\n    - generic [ref=e50]:\n      - link \"Logo\" [ref=e51] [cursor=pointer]:\n        - /url: /\n        - img \"Logo\" [ref=e52]\n      - navigation [ref=e53]:\n        - link \"Apps\" [ref=e85] [cursor=pointer]:\n          - /url: /applications\n        - link \"Sessions\" [ref=e54] [cursor=pointer]:\n          - /url: /sessions\n        - link \"Users\":\n          - /url: /users\n        - link \"About\" [ref=e56] [cursor=pointer]:\n          - /url: /about\n      - button \"ROOT admin expand_more\" [ref=e57]:\n        - generic [ref=e58]: ROOT\n        - generic [ref=e59]:\n          - text: admin\n          - generic [ref=e60]: expand_more\n  - main [ref=e61]:\n    - generic [ref=e86]:\n      - generic [ref=e87]:\n        - generic [ref=e88]:\n          - article [ref=e89]:\n            - heading \"ROOT Root Environment\" [level=1] [ref=e90]:\n              - text: ROOT\n              - generic [ref=e91]: Root Environment\n            - list [ref=e92]:\n              - listitem [ref=e93]: Native\n          - article [ref=e94] [cursor=pointer]:\n            - heading \"TestEnvironment\" [level=1] [ref=e95]\n            - list [ref=e96]:\n              - listitem [ref=e97]: Linked\n            - button \"more_vert\" [expanded] [ref=e113]:\n              - generic [ref=e114]: more_vert\n            - menu \"Menu\" [ref=e115]:\n              - menuitem \"edit Edit\" [ref=e116]:\n                - generic [ref=e117]: edit\n                - text: Edit\n              - menuitem \"sell Make default environment\" [ref=e118]:\n                - generic [ref=e119]: sell\n                - text: Make default environment\n              - separator [ref=e120]\n              - menuitem \"delete Delete\" [ref=e121]:\n                - generic [ref=e122]: delete\n                - text: Delete\n        - button \"add Create environment\" [ref=e98]:\n          - generic [ref=e99]: add\n          - generic [ref=e100]: Create environment\n      - generic [ref=e102]:\n        - navigation [ref=e103]:\n          - tablist [ref=e104]:\n            - listitem [ref=e105]:\n              - tab \"Groups (0)\" [selected] [ref=e106]:\n                - generic [ref=e107]: Groups\n                - generic [ref=e108]: (0)\n            - listitem [ref=e109]:\n              - tab \"Users (0)\" [ref=e110]:\n                - generic [ref=e111]: Users\n                - generic [ref=e112]: (0)\n        - generic:\n          - tabpanel \"Groups (0)\"\n  - contentinfo [ref=e76]:\n    - generic [ref=e78]:\n      - generic [ref=e79]:\n        - paragraph [ref=e80]: Copyright \u00a9 2010 - 2025 AIMMS B.V.\n        - paragraph [ref=e81]: \"AIMMS Cloud Version: 25.6.1.0\"\n      - paragraph [ref=e82]:\n        - text: By using this application you are agreeing to the\n        - link \"Privacy Statement for the Cloud\" [ref=e83] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/cloud/privacy.html\n        - text: and the\n        - link \"Responsible Disclosure Policy\" [ref=e84] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/infosec/responsible-disclosure.html\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_click",
        "args": {
        "element": "Edit",
        "ref": "e116"
        },
        "description": "browser_click called with arguments {'element': 'Edit', 'ref': 'e116'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('menuitem', { name: 'edit Edit' }).click();\n```\n\n### Page state\n- Page URL: https://praveen-2.aimms.cloud/users\n- Page Title: AIMMS Cloud Portal\n- Page Snapshot:\n```yaml\n- generic [ref=e1]:\n  - generic [ref=e48]:\n    - banner [ref=e49]:\n      - generic [ref=e50]:\n        - link \"Logo\" [ref=e51] [cursor=pointer]:\n          - /url: /\n          - img \"Logo\" [ref=e52]\n        - navigation [ref=e53]:\n          - link \"Apps\" [ref=e85] [cursor=pointer]:\n            - /url: /applications\n          - link \"Sessions\" [ref=e54] [cursor=pointer]:\n            - /url: /sessions\n          - link \"Users\":\n            - /url: /users\n          - link \"About\" [ref=e56] [cursor=pointer]:\n            - /url: /about\n        - button \"ROOT admin expand_more\" [ref=e57]:\n          - generic [ref=e58]: ROOT\n          - generic [ref=e59]:\n            - text: admin\n            - generic [ref=e60]: expand_more\n    - main [ref=e61]:\n      - generic [ref=e86]:\n        - generic [ref=e87]:\n          - generic [ref=e88]:\n            - article [ref=e89]:\n              - heading \"ROOT Root Environment\" [level=1] [ref=e90]:\n                - text: ROOT\n                - generic [ref=e91]: Root Environment\n              - list [ref=e92]:\n                - listitem [ref=e93]: Native\n            - article [ref=e94]:\n              - heading \"TestEnvironment\" [level=1] [ref=e95]\n              - list [ref=e96]:\n                - listitem [ref=e97]: Linked\n          - button \"add Create environment\" [ref=e98]:\n            - generic [ref=e99]: add\n            - generic [ref=e100]: Create environment\n        - generic [ref=e102]:\n          - navigation [ref=e103]:\n            - tablist [ref=e104]:\n              - listitem [ref=e105]:\n                - tab \"Groups (0)\" [selected] [ref=e106]:\n                  - generic [ref=e107]: Groups\n                  - generic [ref=e108]: (0)\n              - listitem [ref=e109]:\n                - tab \"Users (0)\" [ref=e110]:\n                  - generic [ref=e111]: Users\n                  - generic [ref=e112]: (0)\n          - generic:\n            - tabpanel \"Groups (0)\"\n    - contentinfo [ref=e76]:\n      - generic [ref=e78]:\n        - generic [ref=e79]:\n          - paragraph [ref=e80]: Copyright \u00a9 2010 - 2025 AIMMS B.V.\n          - paragraph [ref=e81]: \"AIMMS Cloud Version: 25.6.1.0\"\n        - paragraph [ref=e82]:\n          - text: By using this application you are agreeing to the\n          - link \"Privacy Statement for the Cloud\" [ref=e83] [cursor=pointer]:\n            - /url: https://documentation.aimms.com/cloud/privacy.html\n          - text: and the\n          - link \"Responsible Disclosure Policy\" [ref=e84] [cursor=pointer]:\n            - /url: https://documentation.aimms.com/infosec/responsible-disclosure.html\n  - dialog [ref=e124]:\n    - dialog [ref=e125]:\n      - banner [ref=e126]:\n        - heading \"Edit environment\" [level=1] [ref=e128]\n      - group [ref=e132]:\n        - generic [ref=e134]:\n          - generic [ref=e135]: Linked environment URL\n          - textbox \"Linked environment URL\" [active] [ref=e137]: https://google.com\n      - navigation [ref=e138]:\n        - button \"Cancel\" [ref=e139]:\n          - generic [ref=e140]: Cancel\n        - button \"Save\" [ref=e141]:\n          - generic [ref=e142]: Save\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_type",
        "args": {
        "element": "Linked environment URL",
        "ref": "e137",
        "text": "https://google.com"
        },
        "description": "browser_type called with arguments {'element': 'Linked environment URL', 'ref': 'e137', 'text': 'https://google.com'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('textbox', { name: 'Linked environment URL' }).fill('https://google.com');\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_click",
        "args": {
        "element": "Save",
        "ref": "e141"
        },
        "description": "browser_click called with arguments {'element': 'Save', 'ref': 'e141'}",
        "is_verification": False,
        "result": {
        "content": [
            {
            "text": "### Ran Playwright code\n```js\nawait page.getByRole('button', { name: 'Save' }).click();\n```\n\n### Page state\n- Page URL: https://praveen-2.aimms.cloud/users\n- Page Title: AIMMS Cloud Portal\n- Page Snapshot:\n```yaml\n- generic [ref=e48]:\n  - banner [ref=e49]:\n    - generic [ref=e50]:\n      - link \"Logo\" [ref=e51] [cursor=pointer]:\n        - /url: /\n        - img \"Logo\" [ref=e52]\n      - navigation [ref=e53]:\n        - link \"Apps\" [ref=e85] [cursor=pointer]:\n          - /url: /applications\n        - link \"Sessions\" [ref=e54] [cursor=pointer]:\n          - /url: /sessions\n        - link \"Users\":\n          - /url: /users\n        - link \"About\" [ref=e56] [cursor=pointer]:\n          - /url: /about\n      - button \"ROOT admin expand_more\" [ref=e57]:\n        - generic [ref=e58]: ROOT\n        - generic [ref=e59]:\n          - text: admin\n          - generic [ref=e60]: expand_more\n  - main [ref=e61]:\n    - generic [ref=e86]:\n      - generic [ref=e87]:\n        - generic [ref=e88]:\n          - article [ref=e89]:\n            - heading \"ROOT Root Environment\" [level=1] [ref=e90]:\n              - text: ROOT\n              - generic [ref=e91]: Root Environment\n            - list [ref=e92]:\n              - listitem [ref=e93]: Native\n          - article [ref=e94]:\n            - heading \"TestEnvironment\" [level=1] [ref=e95]\n            - list [ref=e96]:\n              - listitem [ref=e97]: Linked\n        - button \"add Create environment\" [ref=e98]:\n          - generic [ref=e99]: add\n          - generic [ref=e100]: Create environment\n      - generic [ref=e102]:\n        - navigation [ref=e103]:\n          - tablist [ref=e104]:\n            - listitem [ref=e105]:\n              - tab \"Groups (0)\" [selected] [ref=e106]:\n                - generic [ref=e107]: Groups\n                - generic [ref=e108]: (0)\n            - listitem [ref=e109]:\n              - tab \"Users (0)\" [ref=e110]:\n                - generic [ref=e111]: Users\n                - generic [ref=e112]: (0)\n        - tabpanel \"Groups (0)\" [ref=e144]:\n          - generic [ref=e147]:\n            - generic [ref=e148]: keyboard_arrow_right\n            - heading \"<everyone>\" [level=1] [ref=e149]\n            - generic [ref=e151]: Environment Everyone Group\n          - button \"add Create group\" [ref=e152]:\n            - generic [ref=e153]: add\n            - generic [ref=e154]: Create group\n  - contentinfo [ref=e76]:\n    - generic [ref=e78]:\n      - generic [ref=e79]:\n        - paragraph [ref=e80]: Copyright \u00a9 2010 - 2025 AIMMS B.V.\n        - paragraph [ref=e81]: \"AIMMS Cloud Version: 25.6.1.0\"\n      - paragraph [ref=e82]:\n        - text: By using this application you are agreeing to the\n        - link \"Privacy Statement for the Cloud\" [ref=e83] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/cloud/privacy.html\n        - text: and the\n        - link \"Responsible Disclosure Policy\" [ref=e84] [cursor=pointer]:\n          - /url: https://documentation.aimms.com/infosec/responsible-disclosure.html\n```\n"
            }
        ]
        }
    },
    {
        "tool": "browser_snapshot",
        "args": {},
        "description": "browser_snapshot called with arguments {}",
        "is_verification": True
    }
    ]
    
    result = build_simple_pack(sample_mcp_log)
    print("Compact format result:")
    import json
    print(json.dumps(result, indent=2))
    
    # Estimate token count (rough approximation: ~4 chars per token)
    json_str = json.dumps(result)
    estimated_tokens = len(json_str) // 4
    print(f"\nEstimated tokens: {estimated_tokens}")
    
    return result


if __name__ == "__main__":
    test_compact_format()