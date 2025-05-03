import re

def extract_test_case_from_selectors(selectors):
    """Extract input values from input actions in selector data.
    This function parses human-readable text and selector metadata to build
    a dictionary of input field names and their corresponding values, based on element IDs.
    """
    def extract_value_from_text(text):
        match = re.search(r'input (.*?) into', text)
        return match.group(1).strip() if match else None

    def extract_field_from_selector(selector):
        match = re.search(r'id=["\'](\w+)["\']', selector)
        return match.group(1).strip() if match else None

    test_case = {}

    for item in selectors:
        if item.get("action") == "input":
            value = extract_value_from_text(item.get("text", ""))
            field = extract_field_from_selector(item.get("selector", ""))
            if field and value:
                test_case[field] = value

    return test_case
