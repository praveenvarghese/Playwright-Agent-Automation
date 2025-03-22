import asyncio
import os
from config import TestCaseAgent, TestCaseCritic
from token_monitoring import token_monitor

TEST_CASES_FILE = "TestCases.txt"
GENERATOR_PROMPT_FILE = "test-case-generator-prompt.txt"
CRITIC_PROMPT_FILE = "test-case-critic-prompt.txt"
RAW_GENERATOR_RESPONSE_FILE = "RawGeneratorResponse.txt"
RAW_CRITIC_RESPONSE_FILE = "RawCriticResponse.txt"

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
        
        with open(CRITIC_PROMPT_FILE, "r", encoding="utf-8") as f:
            critic_prompt = f.read()
    except FileNotFoundError as e:
        print(f"Error: Prompt file not found - {e}")
        return None
    
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
    enhanced_prompt = generator_prompt + context
    
    if context:
        enhanced_prompt += "\n\nPlease use the reference test cases as examples for format and completeness, but create new test cases specific to the requirements above."
    
    # Track token usage for the generator prompt
    prompt_tokens = token_monitor.get_token_count(enhanced_prompt)
    print(f"Generator prompt tokens: {prompt_tokens}")
    
    # Generate test cases
    test_cases = await TestCaseAgent.a_generate_reply(
        messages=[{"role": "user", "content": enhanced_prompt}]
    )
    test_cases_content = test_cases  # Store the generated content
    
    # Track completion token usage
    completion_tokens = token_monitor.get_token_count(test_cases_content)
    print(f"Generator completion tokens: {completion_tokens}")
    
    # Log usage for monitoring
    token_monitor.log_completion_usage(prompt_tokens, completion_tokens)
    
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
    
    # Track token usage for the critic prompt
    critic_prompt_tokens = token_monitor.get_token_count(critic_task)
    print(f"Critic prompt tokens: {critic_prompt_tokens}")
    
    # Get critic review
    reviewed_test_cases = await TestCaseCritic.a_generate_reply(
        messages=[{"role": "user", "content": critic_task}]
    )
    
    final_test_cases_content = reviewed_test_cases  # Store the final version
    
    # Track completion token usage for critic
    critic_completion_tokens = token_monitor.get_token_count(final_test_cases_content)
    print(f"Critic completion tokens: {critic_completion_tokens}")
    
    # Log usage for monitoring
    token_monitor.log_completion_usage(critic_prompt_tokens, critic_completion_tokens)
    
    # Step 6: Save raw critic response
    with open(RAW_CRITIC_RESPONSE_FILE, "w", encoding="utf-8") as f:
        f.write(final_test_cases_content)
    print(f"Raw critic response saved to {RAW_CRITIC_RESPONSE_FILE}")
    
    # Step 7: Save test cases AFTER Critic review
    with open(TEST_CASES_FILE, "w", encoding="utf-8") as f:
        f.write(final_test_cases_content)
    
    print(f"Finalized test cases saved to {TEST_CASES_FILE}")
    
    # Print token usage report
    token_monitor.print_usage_report()
    
    return final_test_cases_content

# If you want to run this file directly for testing
if __name__ == "__main__":
    asyncio.run(generate_test_cases())