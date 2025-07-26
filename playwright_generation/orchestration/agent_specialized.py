"""
LangGraph-based specialized agent workflow for Playwright test generation.
IMPROVED: Now uses proper message-based communication and conversation memory.
"""

import json
import os
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from playwright_generation.agents.agent_config import create_agents
from playwright_generation.orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized
from langgraph.graph import StateGraph, END, START

# IMPROVED: State now includes message history
class TestGenerationState(TypedDict):
    # Input data
    test_case_id: str
    test_case: dict
    selectors: list
    
    # NEW: Message history for agent communication
    messages: List[BaseMessage]
    
    # Intermediate results (kept for backward compatibility)
    pom_response: str
    pom_critique: str
    improved_pom: str
    test_script: str
    test_critique: str
    final_test_script: str
    
    # Output
    page_objects: list
    test_file: str

def create_test_generation_workflow():
    """Create the improved LangGraph workflow with proper agent communication."""
    
    # Get our improved agents
    agents = create_agents()
    
    def generate_pom_node(state: TestGenerationState) -> TestGenerationState:
        """Step 1: Generate Page Object Models with conversation context"""
        print("🔍 Step 1: Generating Page Object Models")
        
        selectors_json = json.dumps(state["selectors"], indent=2)
        test_case = state["test_case"]
        
        # Create initial message with context
        initial_message = HumanMessage(
            content=f"""
Generate Page Object Models for Playwright based on the provided selectors. 

Test Case ID: {state["test_case_id"]}
Test Case Title: {test_case.get('title', '')}

MCP Execution Log (contains actual working Playwright code):
```json
{selectors_json}
```

Instructions:
1. Analyze the selectors to identify logical pages
2. Create a BasePage.js file with common functionality
3. Create specific page objects for each logical page
4. Follow Page Object Model best practices
5. Format your response with clear file headers and JavaScript code blocks

Format each file as:
### 1. FileName.js
```javascript
// Implementation
```
""",
            name="User"
        )
        
        # Start message history with initial request
        current_messages = state.get("messages", []) + [initial_message]
        
        # IMPROVED: Use message-based agent
        response = agents["pom_generator_v2"](current_messages)
        
        # Update state with new message and response
        updated_messages = current_messages + [response]
        
        return {
            **state, 
            "messages": updated_messages,
            "pom_response": response.content  # Keep for backward compatibility
        }

    def critique_pom_node(state: TestGenerationState) -> TestGenerationState:
        """Step 2: Critique Page Object Models with full context"""
        print("🔍 Step 2: Critiquing Page Object Models")
        
        # IMPROVED: Critic can see the generator's work through message history
        critique_request = HumanMessage(
            content="""
Review the Page Object Models generated above and suggest improvements.

Focus on:
1. Structure and organization
2. Selector strategies
3. Method design and naming
4. Error handling
5. Documentation

Provide specific code examples for your suggestions.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [critique_request]
        
        # IMPROVED: Critic sees full conversation
        response = agents["pom_critic_v2"](current_messages)
        
        updated_messages = current_messages + [response]
        
        return {
            **state,
            "messages": updated_messages,
            "pom_critique": response.content
        }

    def improve_pom_node(state: TestGenerationState) -> TestGenerationState:
        """Step 3: Improve Page Object Models based on critique"""
        print("🔍 Step 3: Improving Page Object Models")
        
        improvement_request = HumanMessage(
            content="""
Based on the critique provided above, please improve the Page Object Models.
Address the specific issues mentioned in the critique while maintaining the same format:

### 1. FileName.js
```javascript
// Improved Implementation
```

Focus on implementing the suggestions from the critique.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [improvement_request]
        
        # IMPROVED: Generator can see both original work AND critique
        response = agents["pom_generator_v2"](current_messages)
        
        updated_messages = current_messages + [response]
        
        return {
            **state,
            "messages": updated_messages,
            "improved_pom": response.content
        }

    def generate_test_node(state: TestGenerationState) -> TestGenerationState:
        """Step 4: Generate Test Script with full context"""
        print("🔍 Step 4: Generating Test Script")
        
        test_case_json = json.dumps(state["test_case"], indent=2)
        
        test_request = HumanMessage(
            content=f"""
Create a Playwright test script using the improved Page Object Models from above.

You must use the following testCase values inside your actual test code.

✅ Correct:
    await page.goto(testCase.loginUrl);
    await loginPage.login(testCase.username, testCase.password);
    await environmentPage.createEnvironment(testCase.environmentName);
    await expect(page.locator(testCase.resultSelector)).toHaveText(testCase.expectedText);

❌ Incorrect:
    await page.goto('https://example.com/login');
    await loginPage.login('admin', 'password');
    await environmentPage.createEnvironment('My New Environment');

Test Case:
```json
{test_case_json}
```

Requirements:
1. Do NOT use any hardcoded values. Use fields from `testCase` like:
   - testCase.loginUrl
   - testCase.username
   - testCase.password
   - testCase.environmentName
   - testCase.expectedText

2. Use only the values passed in `testCase` for all navigation, inputs, and assertions.

3. Follow best practices:
   - Arrange → Act → Assert
   - Use ES6 module imports
   - Page Objects should only encapsulate selectors and actions

Format the output as:
### N. testCase.spec.js
```javascript
// Implementation here
```
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_request]
        
        # IMPROVED: Test generator can see all POM work and improvements
        response = agents["test_generator_v2"](current_messages)
        
        updated_messages = current_messages + [response]
        
        return {
            **state,
            "messages": updated_messages,
            "test_script": response.content
        }

    def critique_test_node(state: TestGenerationState) -> TestGenerationState:
        """Step 5: Critique Test Script with full context"""
        print("🔍 Step 5: Critiquing Test Script")
        
        test_critique_request = HumanMessage(
            content="""
Review the test script generated above and suggest improvements.

Focus on:
1. Reliability and robustness
2. Wait strategies
3. Assertion quality
4. Error handling
5. Test structure
6. Proper use of Page Object Models
7. Adherence to the testCase value requirements

Provide specific code examples for your suggestions.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_critique_request]
        
        # IMPROVED: Critic can see the entire conversation including POM work
        response = agents["test_critic_v2"](current_messages)
        
        updated_messages = current_messages + [response]
        
        return {
            **state,
            "messages": updated_messages,
            "test_critique": response.content
        }

    def improve_test_node(state: TestGenerationState) -> TestGenerationState:
        """Step 6: Improve Test Script based on critique"""
        print("🔍 Step 6: Improving Test Script")
        
        test_improvement_request = HumanMessage(
            content="""
Based on the test critique provided above, please improve the test script.
Address the specific issues mentioned while maintaining compatibility with the Page Object Models.

Provide the complete improved implementation as:
### N. testCase.spec.js
```javascript
// Improved Implementation
```

Ensure all critique points are addressed and the test follows best practices.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_improvement_request]
        
        # IMPROVED: Generator can see entire conversation flow
        response = agents["test_generator_v2"](current_messages)
        
        updated_messages = current_messages + [response]
        
        # Extract final outputs using existing extraction functions
        # Use the improved POM response for page objects
        page_objects = extract_page_objects_from_specialized(state["improved_pom"])
        test_file = extract_test_script_from_specialized(response.content)
        
        return {
            **state, 
            "messages": updated_messages,
            "final_test_script": response.content,
            "page_objects": page_objects,
            "test_file": test_file
        }

    # Build the workflow graph
    workflow = StateGraph(TestGenerationState)
    
    # Add nodes
    workflow.add_node("generate_pom", generate_pom_node)
    workflow.add_node("critique_pom", critique_pom_node)
    workflow.add_node("improve_pom", improve_pom_node)
    workflow.add_node("generate_test", generate_test_node)
    workflow.add_node("critique_test", critique_test_node)
    workflow.add_node("improve_test", improve_test_node)
    
    # Add edges
    workflow.add_edge("generate_pom", "critique_pom")
    workflow.add_edge("critique_pom", "improve_pom")
    workflow.add_edge("improve_pom", "generate_test")
    workflow.add_edge("generate_test", "critique_test")
    workflow.add_edge("critique_test", "improve_test")
    
    # Set entry and exit points
    workflow.set_entry_point("generate_pom")
    workflow.add_edge("improve_test", END)
    
    return workflow.compile()


async def generate_with_specialized_agents(agents, test_case_id, test_case, selectors, 
                                          save_callback, pages_dir, tests_dir):
    """
    IMPROVED: Main function with proper message-based agent communication.
    
    Args:
        agents (dict): Not used anymore (we get agents internally)
        test_case_id (str): The test case ID
        test_case (dict): The test case data
        execution_log (list): MCP execution log with actual browser interactions
        save_callback (function): Callback function to save results
        pages_dir (str): Directory to save page objects
        tests_dir (str): Directory to save test scripts

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"🚀 Generating with improved LangGraph workflow for {test_case_id}")

    try:
        # Create the workflow
        workflow = create_test_generation_workflow()
        
        # IMPROVED: Initial state with message history
        initial_state = {
            "test_case_id": test_case_id,
            "test_case": test_case,
            "selectors": selectors,
            "messages": [],  # Start with empty message history
            "pom_response": "",
            "pom_critique": "",
            "improved_pom": "",
            "test_script": "",
            "test_critique": "",
            "final_test_script": "",
            "page_objects": [],
            "test_file": ""
        }
        
        # Run the workflow
        final_state = workflow.invoke(initial_state)
        
        # Save conversation history for debugging
        conversation_file = f"debug_{test_case_id}_conversation.json"
        with open(conversation_file, "w", encoding="utf-8") as f:
            # Convert messages to serializable format
            messages_data = []
            for msg in final_state["messages"]:
                messages_data.append({
                    "type": msg.__class__.__name__,
                    "content": msg.content,
                    "name": getattr(msg, 'name', 'unknown'),
                    "additional_kwargs": getattr(msg, 'additional_kwargs', {})
                })
            json.dump(messages_data, f, indent=2)
        
        print(f"📝 Saved conversation history to {conversation_file}")
        
        # Extract results and save
        page_objects = final_state["page_objects"]
        test_file = final_state["test_file"]
        
        if not page_objects or not test_file:
            print("⚠️ Warning: Some outputs may be empty")
            print(f"Page objects found: {len(page_objects)}")
            print(f"Test file found: {'Yes' if test_file else 'No'}")
        
        # Use the save callback
        save_callback(test_case_id, page_objects, test_file)
        
        print(f"✅ Successfully generated test for {test_case_id} with improved agent communication")
        return True

    except Exception as e:
        print(f"❌ Error in improved LangGraph workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False