"""
Agent orchestrator for AI-enhanced Playwright test generation.
This module orchestrates the conversation flow between Autogen agents.
"""

import os
import json
import asyncio
from agent_config import create_agents
from pom_generation import save_page_objects, analyze_selectors
from utils import save_file
from orchestrator.extraction_utils import extract_page_objects_from_coordinator, extract_test_script_from_chat
from orchestrator.agent_specialized import generate_with_specialized_agents

class PlaywrightAgentOrchestrator:
    """Orchestrates the agent-based generation of enhanced Playwright tests."""
    
    def __init__(self, output_dir="playwright_tests"):
        """Initialize the orchestrator with output directory."""
        self.output_dir = output_dir
        self.agents = create_agents()
        
        # Create output directories
        self.pages_dir = os.path.join(output_dir, "pages")
        self.tests_dir = os.path.join(output_dir, "tests")
        os.makedirs(self.pages_dir, exist_ok=True)
        os.makedirs(self.tests_dir, exist_ok=True)
    
    def _save_results(self, test_case_id, page_objects, test_script):
        """
        Save the generated page objects and test script.
        
        Args:
            test_case_id (str): The test case ID
            page_objects (list): List of page object code blocks
            test_script (str): The enhanced test script
        """
        # Save page objects
        save_page_objects(page_objects, self.pages_dir)
        
        # Save test script
        test_file_path = os.path.join(self.tests_dir, f"{test_case_id}.spec.js")
        save_file(test_file_path, test_script)
        
        print(f"✅ Saved page objects to {self.pages_dir}")
        print(f"✅ Saved test script to {test_file_path}")
    
    async def generate_from_selectors(self, test_case_id, test_case, selectors):
        """
        Generate Page Object Models directly from selectors.
        
        Args:
            test_case_id (str): The test case ID
            test_case (dict): The test case data
            selectors (list): List of selector data
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Use specialized agents approach if available
        if "pom_generator" in self.agents and "pom_critic" in self.agents:
            return await generate_with_specialized_agents(
                self.agents, test_case_id, test_case, selectors, 
                lambda tc_id, page_objects, test_script: self._save_results(tc_id, page_objects, test_script),
                self.pages_dir, self.tests_dir
            )
        
        # Otherwise, fall back to original approach
        return await self._generate_from_selectors_original(test_case_id, test_case, selectors)
    
    async def enhance_test(self, test_case_id, original_script, selectors_data):
        """
        Enhance a Playwright test using AI agents.
        
        Args:
            test_case_id (str): The test case ID
            original_script (str): The original Playwright script
            selectors_data (list): List of selector data
            
        Returns:
            bool: True if successful, False otherwise
        """
        print(f"🚀 Enhancing test for {test_case_id}")
        
        try:
            # Stage 1: Transform to Page Object Model
            print("🔍 Stage 1: Transforming to Page Object Model")
            pom_result = await self._transform_to_pom(test_case_id, original_script, selectors_data)
            if not pom_result:
                print("❌ POM transformation failed")
                return False
                
            # Stage 2: Enhance Test Scripts
            print("🔍 Stage 2: Enhancing Test Scripts")
            script_result = await self._enhance_test_script(test_case_id, pom_result["test_script"])
            if not script_result:
                print("❌ Script enhancement failed")
                return False
                
            # Save final results
            self._save_results(test_case_id, pom_result["page_objects"], script_result["enhanced_script"])
            
            print(f"✅ Successfully enhanced test for {test_case_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error enhancing test: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _transform_to_pom(self, test_case_id, original_script, selectors_data):
        """
        Transform original script to Page Object Model using AI agents.
        
        Args:
            test_case_id (str): The test case ID
            original_script (str): The original Playwright script
            selectors_data (list): List of selector data
            
        Returns:
            dict: Dictionary with page objects and test script
        """
        user_proxy = self.agents["user_proxy"]
        coordinator = self.agents["coordinator"]
        pom_reviewer = self.agents["pom_reviewer"]
        
        # Prepare selectors data for agents
        selectors_json = json.dumps(selectors_data, indent=2)
        
        # Initiate the conversation
        prompt = f"""
Please transform this Playwright test script into a well-structured Page Object Model.

Original Test Script:
```javascript
{original_script}
```

Selectors Data:
```json
{selectors_json}
```

Test Case ID: {test_case_id}

1. Analyze the script and selectors to identify logical pages
2. Create Page Object classes for each page
3. Create a BasePage class for common functionality
4. Rewrite the test to use the Page Object Model pattern
5. Ensure the implementation follows best practices for maintainability
"""
        
        # Start the multi-agent conversation with the coordinator
        chat_result = await user_proxy.initiate_chat(
            coordinator,
            message=prompt,
            max_turns=6,
            summary_method="reflection_with_llm"
        )
        
        # Extract conversation history
        conversation = []
        for message in chat_result.chat_history:
            conversation.append({
                "role": message["role"],
                "content": message["content"]
            })
        
        # Have the POM Reviewer critique the results
        review_prompt = f"""
Review this Page Object Model implementation for the test case {test_case_id}.

{chat_result.summary}

Please provide a detailed critique focusing on:
1. Structure and organization
2. Maintainability and reusability
3. Following Page Object Model best practices
4. Possible improvements

Be specific and provide examples for suggested improvements.
"""
        
        # Send the implementation to the reviewer
        review_result = await user_proxy.initiate_chat(
            pom_reviewer,
            message=review_prompt,
            max_turns=2
        )
        
        # Extract page objects and test script from the conversation
        page_objects = extract_page_objects_from_coordinator(chat_result.chat_history)
        test_script = extract_test_script_from_chat(chat_result.chat_history)
        
        # Incorporate review feedback (if substantial improvements suggested)
        if "improvements suggested" in review_result.summary.lower():
            # Send back to coordinator with reviewer feedback
            improvement_prompt = f"""
The POM Reviewer has provided feedback on the implementation:

{review_result.summary}

Please improve the Page Object Model implementation based on this feedback.
Focus on addressing the key issues raised by the reviewer.
"""
            
            improvement_result = coordinator.generate_reply(
                messages=[{"role": "user", "content": improvement_prompt}]
            )
            
            # Extract improved page objects and test script
            from utils import extract_code_blocks
            improved_objects = extract_code_blocks(improvement_result, "javascript")
            if improved_objects and len(improved_objects) >= 2:
                # If we can identify clear improvements, use them
                page_objects = improved_objects[:-1]  # All but last are page objects
                test_script = improved_objects[-1]    # Last one is test script
        
        return {
            "page_objects": page_objects,
            "test_script": test_script,
            "conversation": conversation
        }
    
    async def _enhance_test_script(self, test_case_id, test_script):
        """
        Enhance the test script with improved assertions and reliability.
        
        Args:
            test_case_id (str): The test case ID
            test_script (str): The test script to enhance
            
        Returns:
            dict: Dictionary with enhanced script and conversation
        """
        user_proxy = self.agents["user_proxy"]
        coordinator = self.agents["coordinator"]
        script_reviewer = self.agents["script_reviewer"]
        
        # Initiate the conversation
        prompt = f"""
Please enhance this Playwright test script with better assertions, wait strategies, and error handling.

Current Test Script:
```javascript
{test_script}
```

Test Case ID: {test_case_id}

Focus on:
1. Implementing proper wait strategies
2. Adding robust assertions
3. Improving error handling
4. Enhancing documentation
5. Following test automation best practices
"""
        
        # Start the multi-agent conversation with coordinator
        chat_result = await user_proxy.initiate_chat(
            coordinator,
            message=prompt,
            max_turns=4,
            summary_method="reflection_with_llm"
        )
        
        # Extract conversation history
        conversation = []
        for message in chat_result.chat_history:
            conversation.append({
                "role": message["role"],
                "content": message["content"]
            })
        
        # Extract enhanced test script
        enhanced_script = extract_test_script_from_chat(chat_result.chat_history)
        
        # Have the Script Reviewer critique the results
        review_prompt = f"""
Review this enhanced test script for the test case {test_case_id}.

{chat_result.summary}

Please provide a detailed critique focusing on:
1. Reliability and robustness
2. Quality of assertions
3. Wait strategies and synchronization
4. Error handling
5. Test structure and organization

Be specific and provide examples for suggested improvements.
"""
        
        # Send the enhanced script to the reviewer
        review_result = await user_proxy.initiate_chat(
            script_reviewer,
            message=review_prompt,
            max_turns=2
        )
        
        # Incorporate review feedback (if substantial improvements suggested)
        if "improvements suggested" in review_result.summary.lower():
            # Send back to coordinator with reviewer feedback
            improvement_prompt = f"""
The Script Reviewer has provided feedback on the implementation:

{review_result.summary}

Please improve the test script based on this feedback.
Focus on addressing the key issues raised by the reviewer.
"""
            
            improvement_result = coordinator.generate_reply(
                messages=[{"role": "user", "content": improvement_prompt}]
            )
            
            # Extract improved test script
            from utils import extract_code_blocks
            improved_scripts = extract_code_blocks(improvement_result, "javascript")
            if improved_scripts and len(improved_scripts) > 0:
                # If we can identify clear improvements, use the last script
                enhanced_script = improved_scripts[-1]
        
        return {
            "enhanced_script": enhanced_script,
            "conversation": conversation
        }
    
    async def _generate_from_selectors_original(self, test_case_id, test_case, selectors):
        """
        Original implementation for generating Page Object Models from selectors.
        
        Args:
            test_case_id (str): The test case ID
            test_case (dict): The test case data
            selectors (list): List of selector data
            
        Returns:
            bool: True if successful, False otherwise
        """
        print(f"🚀 Generating Page Object Models for {test_case_id} from selectors")
        
        try:
            # Analyze selectors to identify pages
            pages = analyze_selectors(selectors)
            
            # Use AI to enhance the page objects and generate a test script
            user_proxy = self.agents["user_proxy"]
            coordinator = self.agents["coordinator"]
            
            # Prepare selectors data for agents
            selectors_json = json.dumps(selectors, indent=2)
            
            # Create prompt for the coordinator
            prompt = f"""
Please create a Page Object Model for Playwright based on these selectors and test case.

Test Case ID: {test_case_id}
Test Case Title: {test_case.get('title', '')}
Test Steps: {test_case.get('steps', '')}
Expected Results: {test_case.get('expectedResults', '')}

Selectors Data:
```json
{selectors_json}
```

1. Create a BasePage class for common functionality
2. Create Page Object classes based on logical pages identified in the selectors
3. Create a test script that uses these Page Objects to implement the test case
4. Make sure to follow enterprise best practices for Playwright testing

Your output should include:
1. All Page Object class files (BasePage.js and any page-specific classes)
2. A complete test script that uses these Page Object classes
"""
            
            # Start the conversation with the coordinator
            chat_result = await user_proxy.initiate_chat(
                coordinator,
                message=prompt,
                max_turns=6
            )
            
            # Extract page objects and test script
            page_objects = extract_page_objects_from_coordinator(chat_result.chat_history)
            test_script = extract_test_script_from_chat(chat_result.chat_history)
            
            # Print debug info
            print(f"Found {len(page_objects)} page objects and test script: {'Yes' if test_script else 'No'}")
            
            # Save the results
            if page_objects and test_script:
                self._save_results(test_case_id, page_objects, test_script)
                return True
            else:
                print(f"❌ Failed to extract page objects or test script from response")
                # Save the chat history for debugging
                debug_file = f"debug_{test_case_id}_chat.txt"
                with open(debug_file, "w", encoding="utf-8") as f:
                    for msg in chat_result.chat_history:
                        f.write(f"{msg['role']} ({msg.get('name', 'Unknown')}):\n{msg['content']}\n\n{'='*80}\n\n")
                print(f"📝 Saved chat history to {debug_file} for debugging")
                return False
                
        except Exception as e:
            print(f"❌ Error generating from selectors: {str(e)}")
            import traceback
            traceback.print_exc()
            return False