"""
6-step LangGraph workflow builder with enhanced validation
"""

import json
import os
import re
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from agents.agent_config import create_agents
from orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized, load_mcp_execution_log
from common.validation_helpers import validate_agent_response

class TestGenerationState(TypedDict):
    test_case_id: str
    test_case: dict
    messages: List[BaseMessage]
    page_objects: list
    test_file: str

def create_pom_test_workflow():
    """Create the 6-step LangGraph workflow with validation"""
    agents = create_agents()
    
    def generate_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 1: Generating Page Object Models with Validation")
        
        execution_log = load_mcp_execution_log(state["test_case_id"])
        execution_json = json.dumps(execution_log, indent=2) if execution_log else "No MCP execution log available"
        test_case = state["test_case"]
        
        structured_steps = test_case.get("structured_steps", [])
        structured_steps_json = json.dumps(structured_steps, indent=2) if structured_steps else "No structured steps available"
        
        initial_message = HumanMessage(
            content=f"""
Generate Page Object Models for Playwright based on the execution log with verification data.

Test Case ID: {state["test_case_id"]}
Test Case Title: {test_case.get('title', '')}

Structured Steps with Expected Results:
```json
{structured_steps_json}
```

MCP Execution Log (contains actions AND verification snapshots):
```json
{execution_json}
```

ENHANCED INSTRUCTIONS:
1. Analyze both actions and verification results in the log
2. Create verification methods for steps that had expected results
3. Use snapshot data to understand what assertions are needed
4. Generate both action methods AND verification methods

Example verification method based on expected results:
```javascript
async verifyEditDialogVisible() {{
  await expect(this.page.getByRole('dialog')).toBeVisible();
  await expect(this.page.getByText('Edit environment')).toBeVisible();
}}

async verifyEnvironmentHasLinkedTag() {{
  await expect(this.page.getByText('Linked')).toBeVisible();
}}
```

Format each file as:
### 1. FileName.js
```javascript
// Implementation with both action and verification methods
```
""",
            name="User"
        )
        
        current_messages = state.get("messages", []) + [initial_message]
        response = agents["pom_generator_v2"](current_messages)
        
        # Validate POM response
        from common.validation_helpers import validate_agent_response
        validate_agent_response(response.content, "pom")
        
        with open(f"{state['test_case_id']}_pom_step1_generate.txt", "w", encoding='utf-8') as f:
            f.write(response.content)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def critique_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 2: Critiquing Page Object Models")
        
        execution_log = load_mcp_execution_log(state["test_case_id"])
        execution_json = json.dumps(execution_log, indent=2) if execution_log else "No MCP execution log available"
        critique_request = HumanMessage(
        content=f"""
Review the Page Object Models generated above, focusing on page separation and URL boundaries.

MCP Execution Log (for URL path analysis):
```json
{execution_json}
```

Focus on:
1. Do verification methods match the expected results from the test case?
2. Are assertions realistic based on the snapshot data?
3. Structure and organization
4. Selector strategies
5. Method design and naming
6. Error handling
7. CRITICAL: Are actions from different URL paths mixed in the same page class?

Provide specific code examples for your suggestions.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [critique_request]
        response = agents["pom_critic_v2"](current_messages)
        with open(f"{state['test_case_id']}_pom_step2_critique.txt", "w", encoding='utf-8') as f:
            f.write(response.content)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def improve_pom_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 3: Improving Page Object Models")
        
        improvement_request = HumanMessage(
            content="""
Based on the critique provided above, please improve the Page Object Models.
Address the specific issues mentioned while maintaining the same format:

### 1. FileName.js
```javascript
// Improved Implementation with enhanced verification methods
```

Focus on implementing the suggestions from the critique, especially around verification methods.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [improvement_request]
        response = agents["pom_generator_v2"](current_messages)
        
        # Validate improved POM response  
        from common.validation_helpers import validate_agent_response
        validate_agent_response(response.content, "pom")
        
        print(f"DEBUG: Response content for extraction: {response.content[:500]}...")
        with open(f"{state['test_case_id']}_pom_step3_improve.txt", "w", encoding='utf-8') as f:
            f.write(response.content)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def generate_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 4: Generating Test Script with Real Assertions")
        
        test_case_json = json.dumps(state["test_case"], indent=2)
        structured_steps = state["test_case"].get("structured_steps", [])
        
        # Extract improved POMs from conversation
        improved_poms = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, 'name') and msg.name == "POM_Generator" and "improved" in msg.content.lower():
                improved_poms = msg.content
                break
        
        # If no improved POMs found, use the latest POM response
        if not improved_poms:
            for msg in reversed(state["messages"]):
                if hasattr(msg, 'name') and msg.name == "POM_Generator":
                    improved_poms = msg.content
                    break
        
        # Load MCP execution log
        mcp_log = load_mcp_execution_log(state["test_case_id"])
        
        test_request = HumanMessage(
            content=f"""
Create a Playwright test script using the Page Object Models.

Page Object Models:
{improved_poms}

MCP EXECUTION LOG (FOLLOW THIS EXACTLY - this is what actually worked):
```json
{json.dumps(mcp_log, indent=2)}
```

Test Case Context (for understanding purpose only):
```json
{test_case_json}
```

CRITICAL: Follow the MCP execution log sequence exactly. Use real values from the MCP log, not the test case description.

REQUIREMENTS:
1. Extract method names from POMs above - use ONLY those exact names
2. Follow the MCP log sequence exactly
3. Use actual values from MCP log (URLs, usernames, element names)
4. Include login sequence from MCP log
5. Use verification methods when MCP log shows verification snapshots
6. Use ES6 module imports
7. Create testCase object with real data from MCP log

Format the output as:
### N. testCase.spec.js
```javascript
// Implementation here
```
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_request]
        response = agents["test_generator_v2"](current_messages)
        
        # Validate test response
        from common.validation_helpers import validate_agent_response
        validate_agent_response(response.content, "test")
        
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def critique_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 5: Critiquing Test Script")
        
        mcp_log = load_mcp_execution_log(state["test_case_id"])
        
        test_critique_request = HumanMessage(
            content=f"""
Review the test script generated above, focusing on verification usage.

MCP Execution Log with Verification Data:
```json
{json.dumps(mcp_log, indent=2) if mcp_log else "No MCP log found"}
```

Focus on:
1. Are verification methods called for steps that had expected results?
2. Are the right verification methods used based on MCP snapshot data?
3. Test structure and flow
4. Proper use of Page Object Models
5. Assertion quality and coverage
6. Adherence to the testCase value requirements

Provide specific code examples for your suggestions.
""",
            name="User"
        )
        
        current_messages = state["messages"] + [test_critique_request]
        response = agents["test_critic_v2"](current_messages)
        updated_messages = current_messages + [response]
        
        return {**state, "messages": updated_messages}

    def improve_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 6: Improving Test Script")
        
        test_improvement_request = HumanMessage(
            content="""
Based on the test critique provided above, please improve the test script.
Address the specific issues mentioned while maintaining compatibility with the Page Object Models.

Ensure verification methods are used appropriately for steps with expected results.

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
        response = agents["test_generator_v2"](current_messages)
        
        # Final validation
        from common.validation_helpers import validate_agent_response
        validate_agent_response(response.content, "test")
        
        updated_messages = current_messages + [response]
        
        # Extract final outputs
        page_objects = extract_page_objects_from_specialized(state["messages"][-4].content)  # From improved POM step
        test_file = extract_test_script_from_specialized(response.content)
        
        # Try fallback extraction if needed
        if not test_file:
            test_file = extract_test_script_from_specialized(state.get("messages", [])[-2].content if len(state.get("messages", [])) > 1 else "")
        
        # More flexible extraction if still no test file
        if not test_file:
            flexible_matches = re.findall(r'### \d+\. \w+\.spec\.js.*?```javascript\s+(.*?)```', response.content, re.DOTALL)
            if flexible_matches:
                test_file = flexible_matches[0].strip()
        
        return {
            **state, 
            "messages": updated_messages,
            "page_objects": page_objects,
            "test_file": test_file
        }

    # Build workflow
    workflow = StateGraph(TestGenerationState)
    
    workflow.add_node("generate_pom", generate_pom_node)
    workflow.add_node("critique_pom", critique_pom_node)
    workflow.add_node("improve_pom", improve_pom_node)
    workflow.add_node("generate_test", generate_test_node)
    workflow.add_node("critique_test", critique_test_node)
    workflow.add_node("improve_test", improve_test_node)
    
    workflow.add_edge("generate_pom", "critique_pom")
    workflow.add_edge("critique_pom", "improve_pom")
    workflow.add_edge("improve_pom", "generate_test")
    workflow.add_edge("generate_test", "critique_test")
    workflow.add_edge("critique_test", "improve_test")
    workflow.add_edge("improve_test", END)
    
    workflow.set_entry_point("generate_pom")
    
    return workflow.compile()