import asyncio
from config import TestCaseAgent, TestCaseCritic

TEST_CASES_FILE = "TestCases.txt"

async def generate_test_cases():
    """
    Step 1: Generate test cases and send to Critic.
    Step 2: Save test cases ONLY after final review.
    """
    print("🔹 Generating test cases... Please wait.")

    # **Step 1: Generate Test Cases (DO NOT SAVE YET)**
    task = """
    You are a QA Automation Agent. Generate test cases for automating the flight booking process on www.blazedemo.com.
    The user should be able to book a flight from Rome to Paris.
    Each test case should have:
    - A clear title
    - Steps to execute
    - Expected outcomes
    """

    test_cases = await TestCaseAgent.a_generate_reply(messages=[{"role": "user", "content": task}])
    test_cases_content = test_cases  # Do not save yet

    # **Step 2: Send test cases to Critic for review**
    print("🔹 Sending test cases to the critic for review...")

    critic_task = f"""
    The following test cases were generated for automating the flight booking process on www.blazedemo.com:

    {test_cases_content}

    Please review these test cases for:
    1. Accuracy - Are the steps correct?
    2. Completeness - Do they cover all major scenarios?
    3. Best Practices - Are they written in a structured format?

    **IMPORTANT:** Provide a **single refined version** of these test cases.
    """

    reviewed_test_cases = await TestCaseCritic.a_generate_reply(
        messages=[{"role": "user", "content": critic_task}],
        max_turns=2  # EXPLICITLY LIMIT TO 2 RESPONSES
    )

    final_test_cases_content = reviewed_test_cases  # Now we save the final version

    # **Step 3: Save test cases AFTER Critic review**
    with open(TEST_CASES_FILE, "w", encoding="utf-8") as f:
        f.write(final_test_cases_content)

    print(f"Finalized test cases saved to {TEST_CASES_FILE}")

    return final_test_cases_content
