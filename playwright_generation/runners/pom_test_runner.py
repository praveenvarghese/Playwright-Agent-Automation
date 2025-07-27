#!/usr/bin/env python3
"""
POM Test Runner - Uses EXACT same flow as main workflow
Just runs the first 3 steps: Generate → Critique → Improve POM
Uses existing TC-ENV-001_selectors.json file
"""

import json
import os
import sys
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from playwright_generation.agents.agent_config import create_agents
from playwright_generation.orchestration.extraction_utils import extract_page_objects_from_specialized

# Use EXACT same state as main workflow
class TestGenerationState(TypedDict):
    # Input data
    test_case_id: str
    test_case: dict
    selectors: list
    
    # Message history for agent communication
    messages: List[BaseMessage]
    
    # Intermediate results (kept for backward compatibility)
    pom_response: str
    pom_critique: str
    improved_pom: str
    test_script: str
    test_critique: str
    final_test_script: str
    
    # Integration loop tracking
    integration_feedback: str
    integration_improvements: str
    integration_final_check: str
    integration_iteration: int
    needs_integration_improvement: bool
    
    # Output
    page_objects: list
    test_file: str

def create_pom_test_workflow():
    """Create workflow using EXACT same nodes as main workflow, just first 3 steps"""
    
    # Get exact same agents
    agents = create_agents()
    
    def generate_pom_node(state: TestGenerationState) -> TestGenerationState:
        """EXACT COPY from main workflow - Step 1: Generate Page Object Models with conversation context"""
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
        """EXACT COPY from main workflow - Step 2: Critique Page Object Models with full context"""
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
        """EXACT COPY from main workflow - Step 3: Improve Page Object Models based on critique"""
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
        
        # Extract page objects from the improved response (same as main workflow)
        page_objects = extract_page_objects_from_specialized(response.content)
        
        return {
            **state,
            "messages": updated_messages,
            "improved_pom": response.content,
            "page_objects": page_objects  # Add extracted page objects
        }

    # Build workflow - EXACT same structure as main workflow
    workflow = StateGraph(TestGenerationState)
    
    # Add only the first 3 nodes
    workflow.add_node("generate_pom", generate_pom_node)
    workflow.add_node("critique_pom", critique_pom_node)
    workflow.add_node("improve_pom", improve_pom_node)
    
    # EXACT same edges as main workflow for first 3 steps
    workflow.add_edge("generate_pom", "critique_pom")
    workflow.add_edge("critique_pom", "improve_pom")
    workflow.add_edge("improve_pom", END)  # Stop here instead of going to generate_test
    
    # Set entry point
    workflow.set_entry_point("generate_pom")
    
    return workflow.compile()

def load_selectors(file_path):
    """Load selectors from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_page_objects(page_objects, output_dir):
    """Save page objects to files"""
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = []
    for i, code_block in enumerate(page_objects):
        # Try to extract class name
        import re
        match = re.search(r'export class\s+(\w+)', code_block)
        if match:
            class_name = match.group(1)
            filename = f"{class_name}.js"
        else:
            filename = f"PageObject_{i+1}.js"
        
        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code_block)
        
        saved_files.append(file_path)
        print(f"✅ Saved: {file_path}")
    
    return saved_files

async def run_pom_test():
    """Main test function - uses EXACT same flow as main workflow"""
    print("🚀 Starting POM Test with EXACT main workflow flow")
    
    # Check if output already exists
    output_dir = "test_output_pom"
    if os.path.exists(output_dir) and os.listdir(output_dir):
        print(f"📁 Found existing files in {output_dir}:")
        for file in os.listdir(output_dir):
            if file.endswith('.js'):
                print(f"  - {file}")
        
        response = input("\nReuse existing files? (y/n) [y]: ").strip().lower()
        if response == '' or response == 'y':
            print("✅ Reusing existing Page Object files")
            return True
        else:
            print("🔄 Regenerating Page Object files...")
    
    # Load existing selectors
    selectors_file = "TC-ENV-001_selectors.json"
    if not os.path.exists(selectors_file):
        print(f"❌ Selector file not found: {selectors_file}")
        print("Make sure you're running this from the project root directory")
        return False
    
    selectors = load_selectors(selectors_file)
    print(f"📁 Loaded {len(selectors)} selectors from {selectors_file}")
    
    # Create workflow using exact same structure
    workflow = create_pom_test_workflow()
    
    # EXACT same initial state as main workflow
    initial_state = {
        "test_case_id": "TC-ENV-001",
        "test_case": {"title": "Create Environment Test"},  # Minimal test case
        "selectors": selectors,
        "messages": [],  # Start with empty message history
        "pom_response": "",
        "pom_critique": "",
        "improved_pom": "",
        "test_script": "",
        "test_critique": "",
        "final_test_script": "",
        "integration_feedback": "",
        "integration_improvements": "",
        "integration_final_check": "",
        "integration_iteration": 0,
        "needs_integration_improvement": False,
        "page_objects": [],
        "test_file": ""
    }
    
    try:
        # Run workflow - EXACT same invoke as main workflow
        print("▶️ Running EXACT same workflow structure...")
        final_state = workflow.invoke(initial_state)
        
        # Save conversation history for debugging - EXACT same as main workflow
        conversation_file = f"debug_TC-ENV-001_conversation.json"
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
        
        # Extract results and save - EXACT same as main workflow
        page_objects = final_state["page_objects"]
        
        if page_objects:
            saved_files = save_page_objects(page_objects, output_dir)
            print(f"🎉 Success! Generated {len(saved_files)} page object files in {output_dir}/")
        else:
            print("⚠️ Warning: No page objects found")
            print(f"Page objects found: {len(page_objects)}")
            
            # Save raw responses for debugging
            with open("debug_pom_response.txt", "w", encoding="utf-8") as f:
                f.write("=== POM Response ===\n")
                f.write(final_state["pom_response"])
                f.write("\n\n=== POM Critique ===\n") 
                f.write(final_state["pom_critique"])
                f.write("\n\n=== Improved POM ===\n")
                f.write(final_state["improved_pom"])
            
            print("📝 Saved debug info to debug_pom_response.txt")
        
        print(f"✅ Successfully completed POM generation for TC-ENV-001 with exact main workflow structure")
        return True
        
    except Exception as e:
        print(f"❌ Error in POM test workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(run_pom_test())
    sys.exit(0 if success else 1)