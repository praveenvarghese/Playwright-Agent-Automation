#!/usr/bin/env python3
"""
POM + Test Runner - Uses EXACT same flow as main workflow
Runs 6 steps: POM Generate → POM Critique → POM Improve → Test Generate → Test Critique → Test Improve
Stops BEFORE integration steps to test basic generation quality
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
from playwright_generation.orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized

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
    """Create workflow using EXACT same nodes as main workflow, first 6 steps only"""
    
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
2. Create specific page objects for each logical page
3. Follow Page Object Model best practices
4. Format your response with clear file headers and JavaScript code blocks

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
        
        return {
            **state,
            "messages": updated_messages,
            "improved_pom": response.content
        }

    def generate_test_node(state: TestGenerationState) -> TestGenerationState:
        """EXACT COPY from main workflow - Step 4: Generate Test Script with full context"""
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
        """EXACT COPY from main workflow - Step 5: Critique Test Script with full context"""
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
        """EXACT COPY from main workflow - Step 6: Improve Test Script based on critique"""
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
        
        # CUSTOM EXTRACTION LOGIC - Copy from integration_check_node but adapted for 6-step workflow
        print("🔍 Extracting final outputs with smart fallback logic...")
        
        # Extract page objects from improved POM (Step 3 output)
        page_objects = extract_page_objects_from_specialized(state["improved_pom"])
        
        # Try multiple sources for test file extraction (like integration_check_node does)
        test_file = None
        
        # Try 1: Extract from current response (final test script)
        test_file = extract_test_script_from_specialized(response.content)
        if test_file:
            print("✅ Extracted test from final test script response")
        
        # Try 2: Fallback to previous test script if current fails
        if not test_file:
            test_file = extract_test_script_from_specialized(state.get("test_script", ""))
            if test_file:
                print("✅ Extracted test from initial test script as fallback")
        
        # Try 3: More flexible extraction - look for any .spec.js file
        if not test_file:
            print("🔍 Trying flexible extraction pattern...")
            import re
            # More flexible pattern - any spec file, not just testCase.spec.js
            flexible_matches = re.findall(r'### \d+\. \w+\.spec\.js.*?```javascript\s+(.*?)```', response.content, re.DOTALL)
            if flexible_matches:
                test_file = flexible_matches[0].strip()
                print("✅ Extracted test using flexible pattern")
        
        # Debug output
        if not test_file:
            print("⚠️ No test file extracted - will save debug info")
        else:
            print(f"✅ Successfully extracted test file ({len(test_file)} characters)")
        
        return {
            **state, 
            "messages": updated_messages,
            "final_test_script": response.content,
            "page_objects": page_objects,
            "test_file": test_file
        }

    # Build workflow - EXACT same structure as main workflow but only 6 steps
    workflow = StateGraph(TestGenerationState)
    
    # Add only the first 6 nodes (no integration steps)
    workflow.add_node("generate_pom", generate_pom_node)
    workflow.add_node("critique_pom", critique_pom_node)
    workflow.add_node("improve_pom", improve_pom_node)
    workflow.add_node("generate_test", generate_test_node)
    workflow.add_node("critique_test", critique_test_node)
    workflow.add_node("improve_test", improve_test_node)
    
    # EXACT same edges as main workflow for first 6 steps
    workflow.add_edge("generate_pom", "critique_pom")
    workflow.add_edge("critique_pom", "improve_pom")
    workflow.add_edge("improve_pom", "generate_test")
    workflow.add_edge("generate_test", "critique_test")
    workflow.add_edge("critique_test", "improve_test")
    workflow.add_edge("improve_test", END)  # Stop here instead of going to integration
    
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

def save_test_script(test_content, output_dir, test_case_id):
    """Save test script to file"""
    os.makedirs(output_dir, exist_ok=True)
    
    test_file_path = os.path.join(output_dir, f"{test_case_id}.spec.js")
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"✅ Saved test: {test_file_path}")
    return test_file_path

async def run_pom_test_workflow():
    """Main test function - uses EXACT same flow as main workflow for 6 steps"""
    print("🚀 Starting POM + Test Workflow (6 steps, no integration)")
    
    # Check if output already exists
    output_pages_dir = "test_output_pom_test/pages"
    output_tests_dir = "test_output_pom_test/tests"
    
    if os.path.exists(output_pages_dir) and os.listdir(output_pages_dir):
        print(f"📁 Found existing files in {output_pages_dir}:")
        for file in os.listdir(output_pages_dir):
            if file.endswith('.js'):
                print(f"  - {file}")
        
        if os.path.exists(output_tests_dir) and os.listdir(output_tests_dir):
            print(f"📁 Found existing files in {output_tests_dir}:")
            for file in os.listdir(output_tests_dir):
                if file.endswith('.js'):
                    print(f"  - {file}")
        
        response = input("\nReuse existing files? (y/n) [y]: ").strip().lower()
        if response == '' or response == 'y':
            print("✅ Reusing existing POM + Test files")
            return True
        else:
            print("🔄 Regenerating POM + Test files...")
    
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
        print("▶️ Running 6-step POM + Test workflow...")
        final_state = workflow.invoke(initial_state)
        
        # Save conversation history for debugging - EXACT same as main workflow
        conversation_file = f"debug_TC-ENV-001_pom_test_conversation.json"
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
        test_file = final_state["test_file"]
        
        if page_objects:
            saved_page_files = save_page_objects(page_objects, output_pages_dir)
            print(f"🎉 Generated {len(saved_page_files)} page object files in {output_pages_dir}/")
        else:
            print("⚠️ Warning: No page objects found")
        
        if test_file:
            saved_test_file = save_test_script(test_file, output_tests_dir, "TC-ENV-001")
            print(f"🎉 Generated test file: {saved_test_file}")
        else:
            print("⚠️ Warning: No test file found")
        
        if not page_objects or not test_file:
            # Save raw responses for debugging
            with open("debug_pom_test_response.txt", "w", encoding="utf-8") as f:
                f.write("=== POM Response ===\n")
                f.write(final_state["pom_response"])
                f.write("\n\n=== POM Critique ===\n") 
                f.write(final_state["pom_critique"])
                f.write("\n\n=== Improved POM ===\n")
                f.write(final_state["improved_pom"])
                f.write("\n\n=== Test Script ===\n")
                f.write(final_state["test_script"])
                f.write("\n\n=== Test Critique ===\n")
                f.write(final_state["test_critique"])
                f.write("\n\n=== Final Test Script ===\n")
                f.write(final_state["final_test_script"])
            
            print("📝 Saved debug info to debug_pom_test_response.txt")
        
        print(f"✅ Successfully completed POM + Test generation (6 steps) for TC-ENV-001")
        return True
        
    except Exception as e:
        print(f"❌ Error in POM + Test workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(run_pom_test_workflow())
    sys.exit(0 if success else 1)