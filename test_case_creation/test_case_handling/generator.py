import asyncio
import os
from test_case_creation.config.config import TestCaseAgent, TestCaseCritic, TestCaseOptimizer

# LangGraph imports
from langgraph.graph import StateGraph, END
from test_case_creation.config.config import TestGenerationState, create_langgraph_llm
from datetime import datetime

# Further down in the file, change:
from test_case_creation.feature_management.feature_processor import FeatureProcessor

# Define paths using project structure
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")
ITERATIONS_DIR = os.path.join(PROJECT_ROOT, "iterations")
os.makedirs(ITERATIONS_DIR, exist_ok=True)

# Make sure directories exist
for directory in [LOGS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

# File paths for saving test cases
TEST_CASES_FILE = os.path.join(OUTPUT_DIR, "TestCases.txt")
GENERATOR_PROMPT_FILE = os.path.join(PROMPTS_DIR, "generator_prompt.txt")
CRITIC_PROMPT_FILE = os.path.join(PROMPTS_DIR, "critic_prompt.txt")
OPTIMIZER_PROMPT_FILE = os.path.join(PROMPTS_DIR, "optimizer_prompt.txt")
FEATURE_REQUIREMENT_FILE = os.path.join(PROMPTS_DIR, "feature_requirement.txt")
RAW_GENERATOR_RESPONSE_FILE = os.path.join(LOGS_DIR, "RawGeneratorResponse.txt")
RAW_CRITIC_RESPONSE_FILE = os.path.join(LOGS_DIR, "RawCriticResponse.txt")


async def generate_test_cases(similar_cases=None, max_iterations=2):
    """
    Enhanced test case generation using LangGraph for structured workflow.
    Preserves exact same agent interactions but with better reliability.
    
    Args:
        similar_cases (list): Optional list of similar test cases to use as context
        max_iterations (int): Maximum number of generator-critic iterations
        
    Returns:
        str: Generated test cases
    """
    print("🔹 Generating test cases with LangGraph orchestration... Please wait.")

    # Load prompts and requirements (UNCHANGED)
    with open(GENERATOR_PROMPT_FILE, "r", encoding="utf-8") as f:
        generator_prompt = f.read()

    with open(FEATURE_REQUIREMENT_FILE, "r", encoding="utf-8") as f:
        feature_requirement = f.read()
    
    with open(CRITIC_PROMPT_FILE, "r", encoding="utf-8") as f:
        critic_prompt = f.read()
        
    with open(OPTIMIZER_PROMPT_FILE, "r", encoding="utf-8") as f:
        optimizer_prompt = f.read()
    
    # Parse acceptance criteria (UNCHANGED)
    try:
        feature_processor = FeatureProcessor()
        parsed_requirement = feature_processor.read_feature_requirement(FEATURE_REQUIREMENT_FILE)
        acceptance_criteria = parsed_requirement.get('acceptance_criteria', [])
        acceptance_criteria_text = "\n".join([f"- {criteria}" for criteria in acceptance_criteria])
    except Exception as e:
        print(f"Warning: Could not parse acceptance criteria: {e}")
        acceptance_criteria_text = ""
    
    # Prepare context (UNCHANGED)
    context = ""
    if similar_cases and len(similar_cases) > 0:
        context = "\n\nREFERENCE TEST CASES:\n"
        for i, case in enumerate(similar_cases):
            context += f"\nREFERENCE TEST CASE {i+1}:\n"
            context += f"ID: {case.get('id', 'Unknown')}\n"
            context += f"Title: {case.get('title', 'Unknown')}\n"
            context += f"Steps:\n{case.get('steps', 'None')}\n"
            context += f"Expected Results:\n{case.get('expectedResults', 'None')}\n"
    
    # Create LangGraph workflow
    workflow = create_test_generation_workflow(
        generator_prompt, critic_prompt, optimizer_prompt, acceptance_criteria_text
    )
    
    # Initial state
    initial_state = TestGenerationState(
        feature_requirement=feature_requirement,
        acceptance_criteria_text=acceptance_criteria_text,
        similar_cases=similar_cases,
        context=context,
        current_test_cases="",
        iteration_count=0,
        max_iterations=max_iterations,
        final_test_cases="",
        critique="",
        raw_responses=[]
    )
    
    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)
    
    # Save outputs (same as before)
    with open(RAW_GENERATOR_RESPONSE_FILE, "w", encoding="utf-8") as f:
        f.write(final_state["final_test_cases"])
    print(f"Initial test cases saved to {RAW_GENERATOR_RESPONSE_FILE}")
    
    # Save critic response
    with open(RAW_CRITIC_RESPONSE_FILE, "w", encoding="utf-8") as f:
        f.write(final_state["critique"])
    print(f"Critic feedback saved")
    
    # Save final test cases
    with open(TEST_CASES_FILE, "w", encoding="utf-8") as f:
        f.write(final_state["final_test_cases"])
    print(f"Finalized test cases saved to {TEST_CASES_FILE}")
    
    return final_state["final_test_cases"]


def create_test_generation_workflow(generator_prompt, critic_prompt, optimizer_prompt, acceptance_criteria_text):
    """Create the LangGraph workflow that mirrors the original AutoGen flow."""
    
    # Initialize LLM
    llm = create_langgraph_llm()
    
    def generator_node(state: TestGenerationState) -> TestGenerationState:
        """Generator agent - creates or improves test cases."""
        
        if state["iteration_count"] == 0:
            # Initial generation
            prompt = f"""
            I'll create test cases based on this feature requirement:

            {state["feature_requirement"]}

            Using the following template:

            {generator_prompt}
            {state["context"]}
            """
        else:
            # Improvement based on critique
            prompt = f"""
            You previously generated these test cases:
            
            {state["current_test_cases"]}
            
            The test case critic provided this feedback:
            
            {state["critique"]}
            
            Please improve the test cases based on this feedback. Ensure all acceptance criteria are covered:
            
            {acceptance_criteria_text}
            
            Generate the complete set of improved test cases.
            """
        
        response = llm.invoke(prompt)
        
        # Save simple changes (only if this is an improvement iteration)
        if state["iteration_count"] > 0:
            save_simple_changes(state["current_test_cases"], response.content, state["critique"], state["iteration_count"])
            print(f"📝 Saved changes to iterations/latest_changes.txt")
        
        return {
            **state,
            "current_test_cases": response.content,
            "raw_responses": state["raw_responses"] + [response.content]
        }
    def critic_node(state: TestGenerationState) -> TestGenerationState:
        """Critic agent - reviews and provides feedback."""
        
        # Prepare critic prompt with acceptance criteria
        critic_prompt_with_criteria = critic_prompt
        if "{acceptance_criteria}" in critic_prompt:
            critic_prompt_with_criteria = critic_prompt.replace("{acceptance_criteria}", acceptance_criteria_text)
        else:
            # If placeholder not found, add criteria at the end
            critic_prompt_with_criteria = critic_prompt + f"\n\nAcceptance Criteria:\n{acceptance_criteria_text}"
        
        critic_task = f"""
        {critic_prompt_with_criteria}
        
        REVIEW THESE TEST CASES:
        
        {state["current_test_cases"]}
        
        Focus on ensuring all acceptance criteria are covered and suggest specific improvements.
        """
        
        response = llm.invoke(critic_task)
        
        return {
            **state,
            "critique": response.content,
            "iteration_count": state["iteration_count"] + 1,
            "raw_responses": state["raw_responses"] + [response.content]
        }
    
    def optimizer_node(state: TestGenerationState) -> TestGenerationState:
        """Optimizer agent - final optimization."""
        
        # Prepare optimizer prompt with acceptance criteria
        optimizer_prompt_with_criteria = optimizer_prompt
        if "{acceptance_criteria}" in optimizer_prompt:
            optimizer_prompt_with_criteria = optimizer_prompt.replace("{acceptance_criteria}", acceptance_criteria_text)
        else:
            # If placeholder not found, add criteria at the end
            optimizer_prompt_with_criteria = optimizer_prompt + f"\n\nAcceptance Criteria:\n{acceptance_criteria_text}"
        
        optimizer_task = f"""
        {optimizer_prompt_with_criteria}
        
        OPTIMIZE THESE TEST CASES:
        
        {state["critique"]}
        """
        
        response = llm.invoke(optimizer_task)
        
        return {
            **state,
            "final_test_cases": response.content,
            "raw_responses": state["raw_responses"] + [response.content]
        }
    
    def should_continue(state: TestGenerationState) -> str:
        """Decision node - continue iteration or move to optimizer."""
        if state["iteration_count"] >= state["max_iterations"]:
            return "optimizer"
        else:
            return "generator"
    
    # Build the graph
    workflow = StateGraph(TestGenerationState)
    
    # Add nodes
    workflow.add_node("generator", generator_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("optimizer", optimizer_node)
    
    # Set entry point
    workflow.set_entry_point("generator")
    
    # Add edges
    workflow.add_edge("generator", "critic")
    workflow.add_conditional_edges(
        "critic",
        should_continue,
        {
            "generator": "generator",
            "optimizer": "optimizer"
        }
    )
    workflow.add_edge("optimizer", END)
    
    return workflow.compile()

def save_simple_changes(before_content, after_content, critique, iteration):
    """Dead simple - just save before and after for manual comparison."""
    
    timestamp = datetime.now().strftime('%H-%M-%S')
    
    # Save before
    before_file = os.path.join(ITERATIONS_DIR, f"iteration_{iteration}_{timestamp}_before.txt")
    with open(before_file, "w", encoding="utf-8") as f:
        f.write(before_content)
    
    # Save after  
    after_file = os.path.join(ITERATIONS_DIR, f"iteration_{iteration}_{timestamp}_after.txt")
    with open(after_file, "w", encoding="utf-8") as f:
        f.write(after_content)
    
    # Save critique
    critique_file = os.path.join(ITERATIONS_DIR, f"iteration_{iteration}_{timestamp}_critique.txt")
    with open(critique_file, "w", encoding="utf-8") as f:
        f.write(critique)
    
    print(f"📝 Saved before/after/critique files for iteration {iteration}")

# Modify just the generator_node function - add these 4 lines:
if __name__ == "__main__":
    asyncio.run(generate_test_cases())