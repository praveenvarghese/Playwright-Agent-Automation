"""
Agent configuration for AI-enhanced Playwright test generation.
This module defines and configures all the Autogen agents used in the system.
"""

import os
import autogen
from dotenv import load_dotenv
from agent_prompts import (
    POM_ENGINEER_PROMPT,
    POM_REVIEWER_PROMPT,
    SCRIPT_ENGINEER_PROMPT,
    SCRIPT_REVIEWER_PROMPT,
    # Add new prompt constants
    POM_GENERATOR_PROMPT,
    POM_CRITIC_PROMPT,
    TEST_GENERATOR_PROMPT,
    TEST_CRITIC_PROMPT
)

# Load environment variables
load_dotenv()

# Configure OpenAI API
config_list = [
    {
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),  # Use the deployment name
        "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "api_type": "azure",
        "base_url": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION")
    }
]

# Configure agents with Azure OpenAI settings
def get_llm_config():
    """Get LLM configuration for agents."""
    return {
        "config_list": config_list,
        "temperature": 0.2,
        "cache_seed": 42  # For reproducibility
    }

def create_agents():
    """Create and configure all agents needed for Playwright test generation."""
    
    # Define agent configurations with Azure OpenAI settings
    llm_config = get_llm_config()
    
    # Coordinator Agent (instead of UserProxyAgent)
    coordinator = autogen.AssistantAgent(
        name="Coordinator",
        system_message="You are a coordinator for the test generation process. You coordinate between the engineering and review agents.",
        llm_config=llm_config
    )
    
    # POM Engineer Agent
    pom_engineer = autogen.AssistantAgent(
        name="POM_Engineer",
        system_message=POM_ENGINEER_PROMPT,
        llm_config=llm_config
    )
    
    # POM Reviewer Agent
    pom_reviewer = autogen.AssistantAgent(
        name="POM_Reviewer",
        system_message=POM_REVIEWER_PROMPT,
        llm_config=llm_config
    )
    
    # Script Engineer Agent
    script_engineer = autogen.AssistantAgent(
        name="Script_Engineer",
        system_message=SCRIPT_ENGINEER_PROMPT,
        llm_config=llm_config
    )
    
    # Script Reviewer Agent
    script_reviewer = autogen.AssistantAgent(
        name="Script_Reviewer",
        system_message=SCRIPT_REVIEWER_PROMPT,
        llm_config=llm_config
    )
    
    # NEW: Specialized Agents for enhanced workflow
    pom_generator = autogen.AssistantAgent(
        name="POM_Generator",
        system_message=POM_GENERATOR_PROMPT,
        llm_config=llm_config
    )
    
    pom_critic = autogen.AssistantAgent(
        name="POM_Critic",
        system_message=POM_CRITIC_PROMPT,
        llm_config=llm_config
    )
    
    test_generator = autogen.AssistantAgent(
        name="Test_Generator",
        system_message=TEST_GENERATOR_PROMPT,
        llm_config=llm_config
    )
    
    test_critic = autogen.AssistantAgent(
        name="Test_Critic",
        system_message=TEST_CRITIC_PROMPT,
        llm_config=llm_config
    )
    
    # Create a UserProxyAgent just for initiating the conversations
    # This one has code execution disabled to prevent Docker issues
    user_proxy = autogen.UserProxyAgent(
        name="User",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=0,
        code_execution_config={"use_docker": False}
    )
    
    return {
        "user_proxy": user_proxy,
        "coordinator": coordinator,
        "pom_engineer": pom_engineer,
        "pom_reviewer": pom_reviewer,
        "script_engineer": script_engineer,
        "script_reviewer": script_reviewer,
        # Add new specialized agents
        "pom_generator": pom_generator,
        "pom_critic": pom_critic,
        "test_generator": test_generator,
        "test_critic": test_critic
    }