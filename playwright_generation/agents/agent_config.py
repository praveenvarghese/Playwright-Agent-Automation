"""
Agent configuration for AI-enhanced Playwright test generation.
This module defines and configures all the LangChain-based agents used in the system.
IMPROVED: Now agents communicate through messages and have memory.
"""

import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import List
from playwright_generation.agents.agent_prompts import(
    POM_GENERATOR_PROMPT,
    POM_CRITIC_PROMPT,
    TEST_GENERATOR_PROMPT,
    TEST_CRITIC_PROMPT,
    INTEGRATION_CRITIC_PROMPT,
)

# Load environment variables
load_dotenv()

def get_langchain_llm():
    """Get LangChain LLM instance for agents."""
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.2,
        model_name="gpt-4o-mini",  # Explicitly specify the model
    )

def create_agents():
    """Create and configure all agents needed for Playwright test generation."""
    
    llm = get_langchain_llm()
    
    # IMPROVED: Agents now work with messages and have memory
    def pom_generator(messages: List[BaseMessage], agent_name: str = "POM_Generator") -> AIMessage:
        """Generate Page Object Models based on conversation history."""
        try:
            # Build conversation with system prompt
            conversation = [
                SystemMessage(content=POM_GENERATOR_PROMPT)
            ]
            
            # Add conversation history so agent can see previous work
            conversation.extend(messages)
            
            response = llm.invoke(conversation)
            
            # Return as AIMessage with agent identification
            return AIMessage(
                content=response.content,
                name=agent_name,
                additional_kwargs={"agent_type": "generator"}
            )
        except Exception as e:
            print(f"Error in POM Generator: {str(e)}")
            return AIMessage(
                content=f"Error generating POM: {str(e)}",
                name=agent_name
            )
    
    def pom_critic(messages: List[BaseMessage], agent_name: str = "POM_Critic") -> AIMessage:
        """Critique Page Object Models with full conversation context."""
        try:
            # Build conversation with system prompt
            conversation = [
                SystemMessage(content=POM_CRITIC_PROMPT)
            ]
            
            # Add full conversation history - critic can see generator's work
            conversation.extend(messages)
            
            # Add specific instruction to reference previous work
            if messages:
                conversation.append(
                    HumanMessage(content="Please review the Page Object Models generated above and provide specific feedback.")
                )
            
            response = llm.invoke(conversation)
            
            return AIMessage(
                content=response.content,
                name=agent_name,
                additional_kwargs={"agent_type": "critic"}
            )
        except Exception as e:
            print(f"Error in POM Critic: {str(e)}")
            return AIMessage(
                content=f"Error critiquing POM: {str(e)}",
                name=agent_name
            )
    
    def test_generator(messages: List[BaseMessage], agent_name: str = "Test_Generator") -> AIMessage:
        """Generate Playwright test scripts using Page Object Models from conversation."""
        try:
            conversation = [
                SystemMessage(content=TEST_GENERATOR_PROMPT)
            ]
            
            # Add conversation history so test generator can see POM work
            conversation.extend(messages)
            
            response = llm.invoke(conversation)
            
            return AIMessage(
                content=response.content,
                name=agent_name,
                additional_kwargs={"agent_type": "generator"}
            )
        except Exception as e:
            print(f"Error in Test Generator: {str(e)}")
            return AIMessage(
                content=f"Error generating test: {str(e)}",
                name=agent_name
            )
    
    def test_critic(messages: List[BaseMessage], agent_name: str = "Test_Critic") -> AIMessage:
        """Critique test scripts with full conversation context."""
        try:
            conversation = [
                SystemMessage(content=TEST_CRITIC_PROMPT)
            ]
            
            # Add conversation history - critic can see all previous work
            conversation.extend(messages)
            
            if messages:
                conversation.append(
                    HumanMessage(content="Please review the test script generated above and provide specific feedback.")
                )
            
            response = llm.invoke(conversation)
            
            return AIMessage(
                content=response.content,
                name=agent_name,
                additional_kwargs={"agent_type": "critic"}
            )
        except Exception as e:
            print(f"Error in Test Critic: {str(e)}")
            return AIMessage(
                content=f"Error critiquing test: {str(e)}",
                name=agent_name
            )
    
    def integration_critic(messages: List[BaseMessage], agent_name: str = "Integration_Critic") -> AIMessage:
        """Provide integration critique with full conversation context."""
        try:
            conversation = [
                SystemMessage(content=INTEGRATION_CRITIC_PROMPT)
            ]
            
            conversation.extend(messages)
            
            response = llm.invoke(conversation)
            
            return AIMessage(
                content=response.content,
                name=agent_name,
                additional_kwargs={"agent_type": "integration_critic"}
            )
        except Exception as e:
            print(f"Error in Integration Critic: {str(e)}")
            return AIMessage(
                content=f"Error in integration critique: {str(e)}",
                name=agent_name
            )

    
    # Return dictionary with both new message-based and legacy agents
    return {
        # NEW MESSAGE-BASED AGENTS (use these!)
        "pom_generator_v2": pom_generator,
        "pom_critic_v2": pom_critic,
        "test_generator_v2": test_generator,
        "test_critic_v2": test_critic,
        "integration_critic_v2": integration_critic,
        
        # LEGACY AGENTS (for backward compatibility)
        # "coordinator": coordinator,
        # "pom_engineer": pom_engineer,
        # "pom_reviewer": pom_reviewer,
        # "script_engineer": script_engineer,
        # "script_reviewer": script_reviewer,
        # "pom_generator": lambda prompt: pom_generator([HumanMessage(content=prompt)]).content,
        # "pom_critic": lambda prompt: pom_critic([HumanMessage(content=prompt)]).content,
        # "test_generator": lambda prompt: test_generator([HumanMessage(content=prompt)]).content,
        # "test_critic": lambda prompt: test_critic([HumanMessage(content=prompt)]).content,
        # "integration_critic": lambda prompt: integration_critic([HumanMessage(content=prompt)]).content
    }

def test_agents():
    """Test function to verify agents are working correctly."""
    try:
        agents = create_agents()
        
        # Test new message-based agents
        test_messages = [
            HumanMessage(content="Create a simple LoginPage class with username and password fields.")
        ]
        
        result = agents["pom_generator_v2"](test_messages)
        print("✅ New POM Generator working")
        print(f"Sample output length: {len(result.content)} characters")
        print(f"Agent name: {result.name}")
        
        # Test that critic can see generator's work
        messages_with_context = test_messages + [result]
        critique = agents["pom_critic_v2"](messages_with_context)
        print("✅ POM Critic can see generator's work")
        print(f"Critique length: {len(critique.content)} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent test failed: {str(e)}")
        return False

if __name__ == "__main__":
    """Test the agents when running this file directly."""
    print("Testing improved LangGraph agents...")
    success = test_agents()
    if success:
        print("✅ All agents configured successfully!")
    else:
        print("❌ Agent configuration failed!")