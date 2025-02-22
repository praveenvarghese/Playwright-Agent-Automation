import asyncio
from test_case_generator import generate_test_cases
from playwright_generator import generate_playwright_script

async def main():
    """
    Main workflow:
    1. Generate test cases & critique them.
    2. Generate Playwright script & critique it.
    """
    # **Step 1: Generate & Review Test Cases**
    test_cases_content = await generate_test_cases()

    # **Step 2: Generate & Review Playwright Script**
    await generate_playwright_script(test_cases_content)

# Run the workflow
if __name__ == "__main__":
    asyncio.run(main())
