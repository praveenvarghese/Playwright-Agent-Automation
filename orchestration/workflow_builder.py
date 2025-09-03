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
from orchestration.extraction_utils import extract_page_objects_from_specialized, extract_pom_methods, load_mcp_execution_log,extract_test_script_from_specialized
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
        
        from agents.agent_prompts import POM_CRITIC_PROMPT
        
        critique_request = HumanMessage(
            content=f"""
    {POM_CRITIC_PROMPT}

    MCP Execution Log for URL Analysis:
    ```json
    {execution_json}
    ```

    Review the Page Object Models generated above using the URL analysis framework from the MCP execution log.
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
    content=f"""
Based on the critique provided above, please improve the Page Object Models.

CRITICAL: Return JSON format:
{{
  "files": [
    {{"path": "pages/ClassName.js", "content": "// improved implementation"}}
  ]
}}

Address the critique points while maintaining JSON structure.
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
        """Generate test script with POM method validation"""
        print("🔍 Step 4: Generating Test Script with Method Validation")
        
        execution_log = load_mcp_execution_log(state["test_case_id"])
        execution_json = json.dumps(execution_log, indent=2) if execution_log else "No MCP execution log available"
        test_case = state["test_case"]
        
        # Extract POM methods for validation
        latest_pom_message = None
        for msg in state["messages"]:
            if hasattr(msg, 'name') and 'POM' in str(msg.name):
                latest_pom_message = msg

        all_pom_methods = {}
        if latest_pom_message:
            pom_blocks = extract_page_objects_from_specialized(latest_pom_message.content)
            for pom_block in pom_blocks:
                methods = extract_pom_methods(pom_block)
                all_pom_methods.update(methods)

        # Create method validation prompt
        validation_text = "AVAILABLE POM METHODS (use ONLY these):\n"
        for class_name, methods in all_pom_methods.items():
            validation_text += f"\n{class_name}:\n"
            for method in methods:
                validation_text += f"  - {method}()\n"
        validation_text += "\n⚠️ CRITICAL: Only call methods listed above. Do not invent new method names."
        
        structured_steps = test_case.get("structured_steps", [])
        structured_steps_json = json.dumps(structured_steps, indent=2) if structured_steps else "No structured steps available"
        
        test_request = HumanMessage(
            content=f"""
    Create a Playwright test script using the Page Object Models with STRICT method validation.

    {validation_text}

    Structured Steps with Expected Results:
    ```json
    {structured_steps_json}
    ```

    MCP EXECUTION LOG (FOLLOW THIS EXACTLY - this is what actually worked):
    ```json
    {execution_json}
    ```

    Test Case Context (for understanding purpose only):
    ```json
    {json.dumps(test_case, indent=2)}
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
    8. Return JSON format:
    {{
    "test_file": {{
        "path": "tests/{state["test_case_id"]}.spec.js",
        "content": "// Implementation here"
    }}
    }}

    Format the output as:
    {{
    "test_file": {{
        "path": "tests/{state["test_case_id"]}.spec.js",
        "content": "// complete test implementation with imports, testCase object, beforeEach hook, and main test"
    }}
    }}
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

    def improve_test_node(state: TestGenerationState) -> TestGenerationState:
        print("🔍 Step 6: Improving Test Script with Validation")
        
        test_improvement_request = HumanMessage(
            content=f"""
    Improve the test script based on the critique above.

    Return JSON format:
    {{
    "test_file": {{
        "path": "tests/{state["test_case_id"]}.spec.js", 
        "content": "// complete improved test implementation"
    }}
    }}
    """,
            name="User"
        )
        
        current_messages = state["messages"] + [test_improvement_request]
        response = agents["test_generator_v2"](current_messages)
        
        # Extract final outputs
        latest_pom_message = None
        for msg in state["messages"]:
            if hasattr(msg, 'name') and 'POM' in str(msg.name):
                latest_pom_message = msg
        
        page_objects = []
        if latest_pom_message:
            page_objects = extract_page_objects_from_specialized(latest_pom_message.content)
        
        test_file = extract_test_script_from_specialized(response.content)
        
        return {
            **state, 
            "messages": current_messages + [response],
            "page_objects": page_objects,
            "test_file": test_file
        }
    
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