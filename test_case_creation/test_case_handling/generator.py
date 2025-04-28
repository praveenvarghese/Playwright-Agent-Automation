import asyncio
import os
from test_case_creation.config.config import TestCaseAgent, TestCaseCritic, TestCaseOptimizer

# Further down in the file, change:
from test_case_creation.feature_management.feature_processor import FeatureProcessor

# Define paths using project structure
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")

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


async def generate_test_cases(similar_cases=None, max_iterations=2):
    """
    Enhanced test case generation with iterative refinement and optimization:
    
    Args:
        similar_cases (list): Optional list of similar test cases to use as context
        max_iterations (int): Maximum number of generator-critic iterations
        
    Returns:
        str: Generated test cases
    """
    print("🔹 Generating test cases with refinement and optimization... Please wait.")

    # Load prompts and requirements
    try:
        with open(GENERATOR_PROMPT_FILE, "r", encoding="utf-8") as f:
            generator_prompt = f.read()

        with open(FEATURE_REQUIREMENT_FILE, "r", encoding="utf-8") as f:
            feature_requirement = f.read()
        
        with open(CRITIC_PROMPT_FILE, "r", encoding="utf-8") as f:
            critic_prompt = f.read()
            
        # Add this new prompt file
        OPTIMIZER_PROMPT_FILE = os.path.join(PROMPTS_DIR, "optimizer_prompt.txt")
        with open(OPTIMIZER_PROMPT_FILE, "r", encoding="utf-8") as f:
            optimizer_prompt = f.read()
    except FileNotFoundError as e:
        print(f"❌ Error: Prompt file not found - {e}")
        return None
    
    # Parse acceptance criteria
    try:
        feature_processor = FeatureProcessor()
        parsed_requirement = feature_processor.read_feature_requirement(FEATURE_REQUIREMENT_FILE)
        acceptance_criteria = parsed_requirement.get('acceptance_criteria', [])
        acceptance_criteria_text = "\n".join([f"- {criteria}" for criteria in acceptance_criteria])
    except Exception as e:
        print(f"Warning: Could not parse acceptance criteria: {e}")
        acceptance_criteria_text = ""
    
    # Prepare context
    context = ""
    if similar_cases and len(similar_cases) > 0:
        context = "\n\nREFERENCE TEST CASES:\n"
        for i, case in enumerate(similar_cases):
            context += f"\nREFERENCE TEST CASE {i+1}:\n"
            context += f"ID: {case.get('id', 'Unknown')}\n"
            context += f"Title: {case.get('title', 'Unknown')}\n"
            context += f"Steps:\n{case.get('steps', 'None')}\n"
            context += f"Expected Results:\n{case.get('expectedResults', 'None')}\n"
    
    # Create initial prompt
    combined_prompt = f"""
    I'll create test cases based on this feature requirement:

    {feature_requirement}

    Using the following template:

    {generator_prompt}
    {context}
    """
    
    # Initial test case generation
    current_test_cases = await TestCaseAgent.a_generate_reply(
        messages=[{"role": "user", "content": combined_prompt}]
    )
    
    # Save raw generator response
    with open(RAW_GENERATOR_RESPONSE_FILE, "w", encoding="utf-8") as f:
        f.write(current_test_cases)
    print(f"Initial test cases saved to {RAW_GENERATOR_RESPONSE_FILE}")
    
    # Prepare critic prompt with acceptance criteria
    critic_prompt_with_criteria = critic_prompt
    if "{acceptance_criteria}" in critic_prompt:
        critic_prompt_with_criteria = critic_prompt.replace("{acceptance_criteria}", acceptance_criteria_text)
    else:
        # If placeholder not found, add criteria at the end
        critic_prompt_with_criteria = critic_prompt + f"\n\nAcceptance Criteria:\n{acceptance_criteria_text}"
    
    # Prepare optimizer prompt with acceptance criteria
    optimizer_prompt_with_criteria = optimizer_prompt
    if "{acceptance_criteria}" in optimizer_prompt:
        optimizer_prompt_with_criteria = optimizer_prompt.replace("{acceptance_criteria}", acceptance_criteria_text)
    else:
        # If placeholder not found, add criteria at the end
        optimizer_prompt_with_criteria = optimizer_prompt + f"\n\nAcceptance Criteria:\n{acceptance_criteria_text}"
    
    # Perform specified number of iterations
    for iteration in range(1, max_iterations + 1):
        print(f"🔹 Iteration {iteration}/{max_iterations}: Critic review...")
        
        # Create critic task
        critic_task = f"""
        {critic_prompt_with_criteria}
        
        REVIEW THESE TEST CASES:
        
        {current_test_cases}
        
        Focus on ensuring all acceptance criteria are covered and suggest specific improvements.
        """
        
        # Get critic review
        critique = await TestCaseCritic.a_generate_reply(
            messages=[{"role": "user", "content": critic_task}]
        )
        
        # Save critic response for this iteration
        critique_file = os.path.join(LOGS_DIR, f"CriticResponse_Iteration{iteration}.txt")
        with open(critique_file, "w", encoding="utf-8") as f:
            f.write(critique)
        print(f"Critic feedback for iteration {iteration} saved")
        
        # If this is the final iteration, proceed to optimization
        if iteration == max_iterations:
            final_critique = critique
            break
            
        # Otherwise, send critique back to generator for improvement
        print(f"🔹 Iteration {iteration}/{max_iterations}: Generator improvement...")
        
        improvement_prompt = f"""
        You previously generated these test cases:
        
        {current_test_cases}
        
        The test case critic provided this feedback:
        
        {critique}
        
        Please improve the test cases based on this feedback. Ensure all acceptance criteria are covered:
        
        {acceptance_criteria_text}
        
        Generate the complete set of improved test cases.
        """
        
        # Get improved test cases
        current_test_cases = await TestCaseAgent.a_generate_reply(
            messages=[{"role": "user", "content": improvement_prompt}]
        )
        
        # Save generator response for this iteration
        generator_file = os.path.join(LOGS_DIR, f"GeneratorResponse_Iteration{iteration}.txt")
        with open(generator_file, "w", encoding="utf-8") as f:
            f.write(current_test_cases)
        print(f"Improved test cases for iteration {iteration} saved")
    
    # Add the optimizer step after completing iterations
    print("🔹 Optimizing test cases to reduce redundancy...")
    
    # Create optimizer task
    optimizer_task = f"""
    {optimizer_prompt_with_criteria}
    
    OPTIMIZE THESE TEST CASES:
    
    {final_critique}
    """
    
    # Get optimizer review
    optimized_test_cases = await TestCaseOptimizer.a_generate_reply(
        messages=[{"role": "user", "content": optimizer_task}]
    )
    
    # Save optimizer response
    optimizer_file = os.path.join(LOGS_DIR, "OptimizerResponse.txt")
    with open(optimizer_file, "w", encoding="utf-8") as f:
        f.write(optimized_test_cases)
    print(f"Optimized test cases saved to {optimizer_file}")
    
    # Use the optimized test cases as the final output
    final_test_cases = optimized_test_cases
    
    # Save final test cases
    with open(TEST_CASES_FILE, "w", encoding="utf-8") as f:
        f.write(final_test_cases)
    print(f"Finalized test cases saved to {TEST_CASES_FILE}")
    
    return final_test_cases
if __name__ == "__main__":
    asyncio.run(generate_test_cases())