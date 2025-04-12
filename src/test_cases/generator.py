import asyncio
import os
from config.config import TestCaseAgent, TestCaseCritic

# Define paths using project structure
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PROMPTS_DIR = os.path.join(PROJECT_ROOT, "prompts")

# Make sure directories exist
for directory in [LOGS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

# File paths for saving test cases
TEST_CASES_FILE = os.path.join(OUTPUT_DIR, "TestCases.txt")
GENERATOR_PROMPT_FILE = os.path.join(PROMPTS_DIR, "generator_prompt.txt")
CRITIC_PROMPT_FILE = os.path.join(PROMPTS_DIR, "critic_prompt.txt")
RAW_GENERATOR_RESPONSE_FILE = os.path.join(LOGS_DIR, "RawGeneratorResponse.txt")
RAW_CRITIC_RESPONSE_FILE = os.path.join(LOGS_DIR, "RawCriticResponse.txt")
FEATURE_REQUIREMENT_FILE = os.path.join(PROMPTS_DIR, "feature_requirement.txt")

async def generate_test_cases(similar_cases=None):
    """
    Enhanced test case generation with response logging:
    Step 1: Load prompts from files
    Step 2: Include similar test cases as context
    Step 3: Generate test cases using prompt and context
    Step 4: Save raw generator response
    Step 5: Get critic review using prompt
    Step 6: Save raw critic response
    Step 7: Save final test cases
    
    Args:
        similar_cases (list): Optional list of similar test cases to use as context
        
    Returns:
        str: Generated test cases
    """
    print("🔹 Generating test cases... Please wait.")

    # Step 1: Load prompts from files
    try:
        with open(GENERATOR_PROMPT_FILE, "r", encoding="utf-8") as f:
            generator_prompt = f.read()

        with open(FEATURE_REQUIREMENT_FILE, "r", encoding="utf-8") as f:
            feature_requirement = f.read()
        
        with open(CRITIC_PROMPT_FILE, "r", encoding="utf-8") as f:
            critic_prompt = f.read()
    except FileNotFoundError as e:
        print(f"❌ Error: Prompt file not found - {e}")
        return None
    
    combined_prompt = f"""
        I'll create test cases based on this feature requirement:

        {feature_requirement}

        Using the following template:

        {generator_prompt}

        Combine the feature_requirement and the generator_prompt to create a new prompt for the test case generation.
        """
    
    # Step 2: Prepare context with similar test cases
    context = ""
    if similar_cases and len(similar_cases) > 0:
        context = "\n\nREFERENCE TEST CASES:\n"
        for i, case in enumerate(similar_cases):
            context += f"\nREFERENCE TEST CASE {i+1}:\n"
            context += f"ID: {case.get('id', 'Unknown')}\n"
            context += f"Title: {case.get('title', 'Unknown')}\n"
            context += f"Steps:\n{case.get('steps', 'None')}\n"
            context += f"Expected Results:\n{case.get('expectedResults', 'None')}\n"
    
    # Step 3: Generate Test Cases using the prompt and context
    enhanced_prompt = combined_prompt + context
    
    if context:
        enhanced_prompt += "\n\nPlease use the reference test cases as examples for format and completeness, but create new test cases specific to the requirements above."
    
    # Generate test cases (no token tracking)
    test_cases = await TestCaseAgent.a_generate_reply(
        messages=[{"role": "user", "content": enhanced_prompt}]
    )
    test_cases_content = test_cases  # Store the generated content
    
    # Step 4: Save raw generator response
    with open(RAW_GENERATOR_RESPONSE_FILE, "w", encoding="utf-8") as f:
        f.write(test_cases_content)
    print(f"Raw generator response saved to {RAW_GENERATOR_RESPONSE_FILE}")
    
    # Step 5: Send test cases to Critic for review using the critic prompt
    print("🔹 Sending test cases to the critic for review...")
    
    critic_task = f"""
    {critic_prompt}
    
    REVIEW THESE TEST CASES:
    
    {test_cases_content}
    """
    
    # Get critic review (no token tracking)
    reviewed_test_cases = await TestCaseCritic.a_generate_reply(
        messages=[{"role": "user", "content": critic_task}]
    )
    
    final_test_cases_content = reviewed_test_cases  # Store the final version
    
    # Step 6: Save raw critic response
    with open(RAW_CRITIC_RESPONSE_FILE, "w", encoding="utf-8") as f:
        f.write(final_test_cases_content)
    print(f"Raw critic response saved to {RAW_CRITIC_RESPONSE_FILE}")
    
    # Step 7: Save test cases AFTER Critic review
    with open(TEST_CASES_FILE, "w", encoding="utf-8") as f:
        f.write(final_test_cases_content)
    
    print(f"Finalized test cases saved to {TEST_CASES_FILE}")
    
    return final_test_cases_content

# If you want to run this file directly for testing
if __name__ == "__main__":
    asyncio.run(generate_test_cases())