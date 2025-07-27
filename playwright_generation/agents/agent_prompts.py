"""
System prompts for AI-enhanced Playwright test generation agents.
This module defines the specialized system prompts for each agent.
"""

import os

# Define the prompt directory path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_DIR = os.path.join(base_dir, "prompts")

def load_prompt(filename):
    """Load prompt from file."""
    prompt_path = os.path.join(PROMPT_DIR, filename)
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Prompt file not found: {prompt_path}")
        return "You are an AI assistant helping with Playwright testing."

# Load prompts from files - ONLY the ones actually used
POM_GENERATOR_PROMPT = load_prompt("pom_generator_prompt.txt")
POM_CRITIC_PROMPT = load_prompt("pom_critic_prompt.txt")
TEST_GENERATOR_PROMPT = load_prompt("test_generator_prompt.txt")
TEST_CRITIC_PROMPT = load_prompt("test_critic_prompt.txt")
INTEGRATION_CRITIC_PROMPT = load_prompt("integration_critic_prompt.txt")
INTEGRATION_IMPROVEMENT_AGENT_PROMPT = load_prompt("integration_improvement_agent_prompt.txt")
INTEGRATION_FRAMEWORK_EXPERT_PROMPT = load_prompt("integration_framework_expert_prompt.txt")