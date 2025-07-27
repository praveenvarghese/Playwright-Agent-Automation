"""
Agent configuration for AI-enhanced Playwright test generation.
CLEANED: Removed legacy agents, kept only working v2 message-based agents.
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
    INTEGRATION_IMPROVEMENT_AGENT_PROMPT,
    INTEGRATION_FRAMEWORK_EXPERT_PROMPT
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
        model_name="gpt-4o-mini",
    )

def create_agents():
    """Create and configure all agents needed for Playwright test generation."""
    
    llm = get_langchain_llm()
    
    def pom_generator(messages: List[BaseMessage], agent_name: str = "POM_Generator") -> AIMessage:
        """Generate Page Object Models based on conversation history."""
        try:
            # Build conversation with system prompt
            conversation = [SystemMessage(content=POM_GENERATOR_PROMPT)]
            conversation.extend(messages)
            
            response = llm.invoke(conversation)
            
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
            conversation = [SystemMessage(content=POM_CRITIC_PROMPT)]
            conversation.extend(messages)
            
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
            conversation = [SystemMessage(content=TEST_GENERATOR_PROMPT)]
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
            conversation = [SystemMessage(content=TEST_CRITIC_PROMPT)]
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
            conversation = [SystemMessage(content=INTEGRATION_CRITIC_PROMPT)]
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

    def integration_framework_expert(messages: List[BaseMessage], agent_name: str = "Integration_Framework_Expert") -> AIMessage:
        """Framework expert that analyzes complete system for integration issues."""
        try:
            conversation = [SystemMessage(content=INTEGRATION_FRAMEWORK_EXPERT_PROMPT)]  # ✅ Use file
            conversation.extend(messages)
            
            response = llm.invoke(conversation)
            
            return AIMessage(
                content=response.content,
                name=agent_name,
                additional_kwargs={"agent_type": "integration_expert"}
            )
        except Exception as e:
            print(f"Error in Integration Framework Expert: {str(e)}")
            return AIMessage(
                content=f"Error in framework analysis: {str(e)}",
                name=agent_name
            )

    def integration_improvement_agent(messages: List[BaseMessage], agent_name: str = "Integration_Improvement") -> AIMessage:
        """Specialized agent that fixes cross-file integration issues."""
        try:
            conversation = [SystemMessage(content=INTEGRATION_IMPROVEMENT_AGENT_PROMPT)]  # ✅ Use file
            conversation.extend(messages)
            
            response = llm.invoke(conversation)
            
            return AIMessage(
                content=response.content,
                name=agent_name,
                additional_kwargs={"agent_type": "integration_improvement"}
            )
        except Exception as e:
            print(f"Error in Integration Improvement: {str(e)}")
            return AIMessage(
                content=f"Error in integration improvement: {str(e)}",
                name=agent_name
            )
    # Return only the working v2 message-based agents
    return {
        "pom_generator_v2": pom_generator,
        "pom_critic_v2": pom_critic,
        "test_generator_v2": test_generator,
        "test_critic_v2": test_critic,
        "integration_critic_v2": integration_critic,
        "integration_framework_expert": integration_framework_expert,  # NEW
        "integration_improvement_agent": integration_improvement_agent,  # NEW
    }

def test_agents():
    """Test function to verify agents are working correctly."""
    try:
        agents = create_agents()
        
        # Test message-based agents
        test_messages = [
            HumanMessage(content="Create a simple LoginPage class with username and password fields.")
        ]
        
        result = agents["pom_generator_v2"](test_messages)
        print("✅ POM Generator working")
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
    print("Testing cleaned LangGraph agents...")
    success = test_agents()
    if success:
        print("✅ All agents configured successfully!")
    else:
        print("❌ Agent configuration failed!")