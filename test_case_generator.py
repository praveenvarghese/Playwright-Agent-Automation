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
    Context: You are an AI model specializing in generating structured manual test cases based on requirement specifications.
Goal: Generate comprehensive test cases, ensuring both functional and edge case coverage.
Input: The following Requirement Specification and Acceptance Criteria.

Requirement Specification:

Environment Management allows users to create, edit, set default, and delete environments.
Environments are categorized as "Native" (if no linked URL is provided) or "Linked" (if a URL is associated).
Acceptance Criteria:

Users can create, edit, set default, and delete environments.
Created environments should be visible in the environment list.
Environment names should support spaces.
"Native" or "Linked" tags should be displayed based on the 'Linked environment URL' field.
Deleting an environment should show a confirmation dialog.
If the default environment is deleted, the ROOT environment becomes the default.
Processing Logic:

Analyze the requirement specification and acceptance criteria.
Identify functional and edge case scenarios.
Generate structured test cases in the following format:
Output Format:
Each test case should include:

Test Name
Preconditions (if any)
Test Steps
Expected Result
Actual Result (to be filled during execution)
Generate at least one test case per acceptance criterion and ensure edge case coverage.
    """

    test_cases = await TestCaseAgent.a_generate_reply(messages=[{"role": "user", "content": task}])
    test_cases_content = test_cases  # Do not save yet

    # **Step 2: Send test cases to Critic for review**
    print("🔹 Sending test cases to the critic for review...")

    critic_task = f"""
    The following test cases were generated for creating and managing environments based on the provided requirement specification:

    {test_cases_content}

    Context: You are an AI model specializing in test case critique and refinement.
Evaluation Criteria:

Coverage: Do the test cases cover all acceptance criteria and potential edge cases?
Clarity: Are the test steps and expected results well-defined and easy to follow?
Correctness: Are the test scenarios valid based on the requirement?
Efficiency: Are the test cases optimized, avoiding redundant or unnecessary steps?
Output Format:

List of identified issues (if any).
Suggestions for improvement.
Final refined test cases incorporating feedback.
If the test cases are already well-structured, confirm that they meet the criteria and suggest any minor improvements.
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
