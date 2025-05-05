# scenario_generation.py
import os
from config import config_list  # Importing the config_list from config.py
import autogen

# Define the agent to generate test scenarios
TestScenarioAgent = autogen.AssistantAgent(
    name="TestScenario_Generator",
    llm_config={"config_list": config_list}
)

def load_prompt(prompt_filename):
    """
    Load the prompt from the given file in the prompts directory.
    """
    prompts_folder_path = os.path.join(os.path.dirname(__file__), "prompts")
    with open(os.path.join(prompts_folder_path, prompt_filename), "r", encoding="utf-8") as f:
        return f.read()

def generate_test_scenarios(requirement_text):
    """
    Generate test scenarios based on the requirement text.
    """
    # Load the prompt for TestScenarioAgent
    prompt = load_prompt("test_scenario_prompt.txt")
    prompt = prompt.format(requirement_text=requirement_text)  # Inject requirement text into the prompt

    # Generate test scenarios
    response = TestScenarioAgent.generate_reply(messages=[{"role": "user", "content": prompt}])
    generated_scenarios = response.strip()

    # Remove 'TERMINATE' from the generated content
    if "TERMINATE" in generated_scenarios:
        generated_scenarios = generated_scenarios.replace("TERMINATE", "").strip()

    return generated_scenarios
