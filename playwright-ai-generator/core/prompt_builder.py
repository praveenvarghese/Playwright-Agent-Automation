def build_test_prompt(test_case: dict, ui_elements: list) -> str:
    """
    Constructs a prompt for an LLM to generate a Playwright test case.

    Args:
        test_case (dict): Test case details with id, title, steps, expectedResults.
        ui_elements (list): List of structured UI elements (from browser inspector).

    Returns:
        str: A formatted prompt string to send to an LLM.
    """
    prompt = f"""You are an expert QA automation engineer using Playwright with the Page Object Model.

Your task is to generate a high-quality Playwright test script based on the following test case and available UI elements:

Test Case ID: {test_case.get('id')}
Title: {test_case.get('title')}
Steps:
{test_case.get('steps')}
Expected Results:
{test_case.get('expectedResults')}

The following UI elements were detected on the page:
"""

    for elem in ui_elements:
        summary = f"- {elem.get('type', 'unknown')}"
        if elem.get('text'):
            summary += f" with text '{elem['text']}'"
        if elem.get('name', ''):
            summary += f" (name='{elem['name']}')"
        if elem.get('placeholder', ''):
            summary += f" (placeholder='{elem['placeholder']}')"
        if elem.get('selector'):
            summary += f" → selector: `{elem['selector']}`"
        prompt += summary + "\n"

    prompt += "\nGenerate a complete test using Playwright best practices.\n"
    prompt += "IMPORTANT: Use the exact selectors from the detected UI elements rather than generic placeholders.\n"
    return prompt

def build_critique_prompt(test_case: dict, original_script: str) -> str:
    """
    Builds a prompt asking the LLM to critique and improve a generated test script.

    Args:
        test_case (dict): The original test case
        original_script (str): The test script that was generated

    Returns:
        str: Prompt text to send to the LLM for review
    """
    prompt = f"""You are a senior QA engineer specializing in Playwright automation and clean code.

Please review the following Playwright test script and provide an improved version if needed.

Test Case ID: {test_case.get('id')}
Title: {test_case.get('title')}

Steps:
{test_case.get('steps')}

Expected Results:
{test_case.get('expectedResults')}

Generated Script:
```javascript
{original_script}
```

Analyze the script for the following:

1. Completeness — Does it cover all test steps?
2. Correctness — Does it check all expected results?
3. Best Practices — Is the code clean, structured, and robust?
4. Page Object Model — Is it using the Page Object Model correctly?
5. Selectors — Make sure to use actual CSS selectors detected from the application (e.g., button.button--environment-list-add, input#envName) rather than generic placeholder selectors (e.g., button[data-testid="create-environment"]).
6. Improvements — Suggest any enhancements or fixes if needed.

If the script is already good, you may return it as-is.

Return only the updated JavaScript code — do not include explanations or summaries.
"""
    return prompt