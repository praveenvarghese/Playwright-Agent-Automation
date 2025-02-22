import asyncio
import re
from config import UIAgent, UICritic

PLAYWRIGHT_FILE = "PlaywrightScript.js"

async def generate_playwright_script(test_cases_content):
    """
    Step 1: Generate Playwright test script based on final test cases.
    Step 2: Get Critic review before saving.
    Step 3: Extract only JavaScript content before writing.
    """
    print("🔹 Generating Playwright script... Please wait.")

    # **Step 1: Generate Playwright Script Using Final Test Cases**
    playwright_task = f"""
    The following test cases have been finalized for automating the flight booking process on www.blazedemo.com:

    {test_cases_content}

    Based on these test cases, generate a complete Playwright test suite in JavaScript.
    - Each test case should have its own function in Playwright.
    - Use async/await for handling automation steps.
    - Use meaningful selectors for accuracy.
    - Ensure proper validation with assertions.

    Provide the Playwright script as a **single JavaScript code block** inside triple backticks (```) without extra commentary.
    """

    playwright_script = await UIAgent.a_generate_reply(
        messages=[{"role": "user", "content": playwright_task}]
    )

    playwright_script_content = playwright_script  # Store response in memory

    # **Step 2: Extract Only the JavaScript Code Block**
    match = re.search(r"```javascript(.*?)```", playwright_script_content, re.DOTALL)

    if match:
        playwright_script_content = match.group(1).strip()  # ✅ Extract JS Code Only
    else:
        print("⚠️ Warning: No JavaScript code block detected. Saving full response.")
    
    # **Step 3: Send Playwright Script to Critic for Refinement**
    print("🔹 Sending Playwright script to the critic for review...")

    critique_task = f"""
    The following Playwright test script has been generated for automating flight booking on www.blazedemo.com:

    ```javascript
    {playwright_script_content}
    ```

    Please review this script for:
    1. Correct implementation of test cases.
    2. Proper use of Playwright automation best practices.
    3. Well-structured and maintainable JavaScript code.

    **IMPORTANT:** Provide the final refined version of this Playwright script.
    """

    reviewed_script = await UICritic.a_generate_reply(
        messages=[{"role": "user", "content": critique_task}],
        max_turns=2  # Limit to 2 responses
    )

    final_playwright_script_content = reviewed_script  # Store final refined script

    # **Step 4: Extract Clean JavaScript Code from the Critic Response**
    match = re.search(r"```javascript(.*?)```", final_playwright_script_content, re.DOTALL)
    
    if match:
        final_playwright_script_content = match.group(1).strip()
    else:
        print("⚠️ Warning: No refined JavaScript code block detected. Saving full response.")

    # **Step 5: Save Playwright Script AFTER Critic Review**
    with open(PLAYWRIGHT_FILE, "w", encoding="utf-8") as f:
        f.write(final_playwright_script_content)

    print(f"Finalized Playwright script saved to {PLAYWRIGHT_FILE}")

    return final_playwright_script_content
