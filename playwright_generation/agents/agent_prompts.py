"""
System prompts for AI-enhanced Playwright test generation agents.
"""

import os

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

POM_GENERATOR_PROMPT = load_prompt("pom_generator_prompt.txt")
POM_CRITIC_PROMPT = load_prompt("pom_critic_prompt.txt")
TEST_GENERATOR_PROMPT = load_prompt("test_generator_prompt.txt")
TEST_CRITIC_PROMPT = load_prompt("test_critic_prompt.txt")