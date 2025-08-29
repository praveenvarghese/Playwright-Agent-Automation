# critique_handling.py
import os
from config import config_list  # Importing the config_list from config.py
import autogen

CritiqueAgent = autogen.AssistantAgent(
    name="Critique_Agent",
    llm_config={"config_list": config_list},
    system_message="You are a QA expert who reviews test scenarios for completeness, clarity, and coverage. Identify gaps and suggest improvements."
)

def load_prompt(prompt_filename):
    """
    Load the prompt from the given file in the prompts directory.
    """
    prompts_folder_path = os.path.join(os.path.dirname(__file__), "prompts")
    with open(os.path.join(prompts_folder_path, prompt_filename), "r", encoding="utf-8") as f:
        return f.read()

def critique_test_scenarios(scenarios):
    """
    Send the generated test scenarios for critique.
    """
    # Load the prompt for CritiqueAgent
    prompt = load_prompt("critique_prompt.txt")
    prompt = prompt.format(generated_test_scenarios=scenarios)  # Inject test scenarios into the prompt

    # Send to CritiqueAgent for review
    response = CritiqueAgent.generate_reply(messages=[{"role": "user", "content": prompt}])
    critique_feedback = response.strip()

    return critique_feedback
