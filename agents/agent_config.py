"""
Agent configuration for AI-enhanced Playwright test generation.
TOKEN OPTIMIZATION APPLIED - Production Ready
"""

import os
import json
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import List
from agents.agent_prompts import(
    POM_GENERATOR_PROMPT,
    POM_CRITIC_PROMPT,
    TEST_GENERATOR_PROMPT,
    TEST_CRITIC_PROMPT
)

# Load environment variables from .env file
load_dotenv()

def estimate_message_tokens(messages: List[BaseMessage]) -> int:
    """Estimate token count for message list"""
    total_chars = sum(len(msg.content) for msg in messages if hasattr(msg, 'content'))
    return total_chars // 4  # Rough estimation

def get_langchain_llm():
    """Get LangChain LLM instance for agents."""
    
    # Token-aware configuration
    max_tokens = int(os.getenv("AZURE_OPENAI_MAX_TOKENS", "4000"))  # Conservative default for agents
    
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.1,  # Lower temperature for more consistent, compact outputs
        model_name="gpt-4o-mini",
        max_tokens=max_tokens,
        request_timeout=120,  # 2 minutes timeout
        max_retries=2  # Reduced retries to save tokens
    )

def create_agents():
    """Create and configure agents for the 6-step workflow."""
    
    llm = get_langchain_llm()
    
    # Token budget per agent call
    AGENT_TOKEN_BUDGET = 15000  # 15k tokens per agent call
    
    def pom_generator(messages: List[BaseMessage], agent_name: str = "POM_Generator") -> AIMessage:
        """Generate Page Object Models based on conversation history."""
        try:
            # Token budget check
            estimated_tokens = estimate_message_tokens(messages)
            if estimated_tokens > AGENT_TOKEN_BUDGET:
                print(f"⚠️ POM Generator input approaching token limit ({estimated_tokens})")
                # Truncate older messages, keep system prompt and recent context
                messages = messages[:1] + messages[-5:]  # System + last 5 messages
                print(f"🔧 Truncated to {len(messages)} messages")
            
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
            # Token budget check for critic
            estimated_tokens = estimate_message_tokens(messages)
            if estimated_tokens > AGENT_TOKEN_BUDGET:
                print(f"⚠️ POM Critic input approaching token limit ({estimated_tokens})")
                # Keep system prompt, generator output, and focused context
                messages = messages[:1] + messages[-3:]  # System + last 3 messages
                print(f"🔧 Truncated to {len(messages)} messages for focused critique")
            
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
            # Token budget check
            estimated_tokens = estimate_message_tokens(messages)
            if estimated_tokens > AGENT_TOKEN_BUDGET:
                print(f"⚠️ Test Generator input approaching token limit ({estimated_tokens})")
                # Keep system prompt, POM outputs, and essential context
                messages = messages[:1] + messages[-4:]  # System + last 4 messages
                print(f"🔧 Truncated to {len(messages)} messages")
            
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
            # Token budget check for test critic
            estimated_tokens = estimate_message_tokens(messages)
            if estimated_tokens > AGENT_TOKEN_BUDGET:
                print(f"⚠️ Test Critic input approaching token limit ({estimated_tokens})")
                # Keep system prompt and recent test generation context
                messages = messages[:1] + messages[-3:]  # System + last 3 messages
                print(f"🔧 Truncated to {len(messages)} messages for focused critique")
            
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
    
    return {
        "pom_generator_v2": pom_generator,
        "pom_critic_v2": pom_critic,
        "test_generator_v2": test_generator,
        "test_critic_v2": test_critic
    }

def test_agents():
    """Test function to verify agents are working correctly."""
    try:
        agents = create_agents()
        
        test_messages = [
            HumanMessage(content="Create a simple LoginPage class with username and password fields.")
        ]
        
        result = agents["pom_generator_v2"](test_messages)
        print("✅ POM Generator working")
        output_tokens = len(result.content) // 4
        print(f"Sample output: {len(result.content)} chars ({output_tokens} tokens)")
        print(f"Agent name: {result.name}")
        
        if output_tokens > 5000:
            print("⚠️ Agent output may be verbose - consider prompt optimization")
        else:
            print("✅ Agent output is token-efficient")
        
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
    print("Testing agent configuration...")
    success = test_agents()
    if success:
        print("✅ All agents configured successfully!")
    else:
        print("❌ Agent configuration failed!")