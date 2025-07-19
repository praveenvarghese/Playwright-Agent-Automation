"""
Agent orchestrator for AI-enhanced Playwright test generation.
This module orchestrates the LangChain/LangGraph-based generation flow.
"""

import os
import json
import re
import asyncio
from playwright_generation.agents.agent_config import create_agents
from playwright_generation.generators.pom_generation import save_page_objects, analyze_selectors
from playwright_generation.common.utils import save_file, extract_code_blocks, load_prompt_template
from playwright_generation.orchestration.extraction_utils import extract_page_objects_from_coordinator, extract_test_script_from_chat
from playwright_generation.orchestration.agent_specialized import generate_with_specialized_agents
from playwright_generation.generators.validation import run_integration_validation
from playwright_generation.agents.critique_feedback import apply_critique_improvements

class PlaywrightAgentOrchestrator:
    """Orchestrates the LangChain/LangGraph-based generation of enhanced Playwright tests."""
    
    def __init__(self, output_dir="playwright_tests"):
        """Initialize the orchestrator with output directory."""
        self.output_dir = output_dir
        self.agents = create_agents()  # LangChain agents
        
        # Create output directories
        self.pages_dir = os.path.join(output_dir, "pages")
        self.tests_dir = os.path.join(output_dir, "tests")
        os.makedirs(self.pages_dir, exist_ok=True)
        os.makedirs(self.tests_dir, exist_ok=True)
    
    def _save_results(self, test_case_id, page_objects, test_script):
        """
        Save the generated page objects and test script and run the feedback loop.
        
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
        
        # Run integration validation
        validation_result = self.validate_integration(test_case_id)
        
        # If validation was successful, run the feedback loop
        if validation_result["status"] == "success":
            print("\n🔄 Starting feedback loop to improve code based on critique...")
            improvement_result = self.improve_from_critique(validation_result["critique_file"])
            
            if improvement_result["status"] == "success":
                print("🎉 Feedback loop complete - code has been improved based on critique")
            else:
                print("⚠️ Feedback loop encountered issues - some improvements may not have been applied")
        else:
            print("⚠️ Integration validation failed - skipping feedback loop")

    async def generate_from_selectors(self, test_case_id, test_case, selectors):
        """Generate Page Object Models directly from selectors using LangGraph workflow."""
        
        # Force using the new workflow with updated agents
        from playwright_generation.orchestration.agent_specialized import generate_with_specialized_agents
        
        return await generate_with_specialized_agents(
            None,  # Don't pass agents, let it create its own
            test_case_id, 
            test_case, 
            selectors, 
            lambda tc_id, page_objects, test_script: self._save_results(tc_id, page_objects, test_script),
            self.pages_dir, 
            self.tests_dir
        )
    
    async def enhance_test(self, test_case_id, original_script, selectors_data):
        """
        Enhance a Playwright test using LangChain agents.
        
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
        Transform original script to Page Object Model using LangChain agents.
        
        Args:
            test_case_id (str): The test case ID
            original_script (str): The original Playwright script
            selectors_data (list): List of selector data
            
        Returns:
            dict: Dictionary with page objects and test script
        """
        # Prepare selectors data for agents
        selectors_json = json.dumps(selectors_data, indent=2)
        
        # Create prompt for POM transformation
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

Format your response with clear file headers:
### BasePage.js
```javascript
// BasePage implementation
```

### LoginPage.js
```javascript
// LoginPage implementation
```

### testCase.spec.js
```javascript
// Test script using Page Objects
```
"""
        
        # Use LangChain POM generator directly
        response = self.agents["pom_generator"](prompt)
        
        # Get review from POM reviewer
        review_prompt = f"""
Review this Page Object Model implementation for the test case {test_case_id}.

{response}

Please provide a detailed critique focusing on:
1. Structure and organization
2. Maintainability and reusability
3. Following Page Object Model best practices
4. Possible improvements

Be specific and provide examples for suggested improvements.
"""
        
        review = self.agents["pom_reviewer"](review_prompt)
        
        # If substantial improvements suggested, get improved version
        if "improvements suggested" in review.lower() or "improve" in review.lower():
            improvement_prompt = f"""
The POM Reviewer has provided feedback on the implementation:

{review}

Please improve the Page Object Model implementation based on this feedback.
Focus on addressing the key issues raised by the reviewer.

Original implementation:
{response}

Provide the improved implementation with the same format:
### BasePage.js
```javascript
// Improved BasePage implementation
```

### LoginPage.js
```javascript
// Improved LoginPage implementation  
```

### testCase.spec.js
```javascript
// Improved test script
```
"""
            
            response = self.agents["pom_generator"](improvement_prompt)
        
        # Extract page objects and test script
        page_objects = extract_page_objects_from_coordinator([{"role": "assistant", "content": response}])
        test_script = extract_test_script_from_chat([{"role": "assistant", "content": response}])
        
        return {
            "page_objects": page_objects,
            "test_script": test_script,
            "response": response
        }
    
    async def _enhance_test_script(self, test_case_id, test_script):
        """
        Enhance the test script with improved assertions and reliability using LangChain agents.
        
        Args:
            test_case_id (str): The test case ID
            test_script (str): The test script to enhance
            
        Returns:
            dict: Dictionary with enhanced script
        """
        # Create enhancement prompt
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

Provide the enhanced test script in the same format.
"""
        
        # Use LangChain script engineer
        enhanced_response = self.agents["script_engineer"](prompt)
        
        # Get review from script reviewer
        review_prompt = f"""
Review this enhanced test script for the test case {test_case_id}.

{enhanced_response}

Please provide a detailed critique focusing on:
1. Reliability and robustness
2. Quality of assertions
3. Wait strategies and synchronization
4. Error handling
5. Test structure and organization

Be specific and provide examples for suggested improvements.
"""
        
        review = self.agents["script_reviewer"](review_prompt)
        
        # If improvements suggested, get improved version
        if "improvements suggested" in review.lower() or "improve" in review.lower():
            improvement_prompt = f"""
The Script Reviewer has provided feedback:

{review}

Please improve the test script based on this feedback.

Original enhanced script:
{enhanced_response}

Provide the final improved test script.
"""
            
            enhanced_response = self.agents["script_engineer"](improvement_prompt)
        
        # Extract enhanced test script
        enhanced_scripts = extract_code_blocks(enhanced_response, "javascript")
        enhanced_script = enhanced_scripts[-1] if enhanced_scripts else enhanced_response
        
        return {
            "enhanced_script": enhanced_script,
            "response": enhanced_response
        }
        
    def validate_integration(self, test_case_id=None):
        """
        Validate the integration between generated Page Objects and Test Scripts.
        
        Args:
            test_case_id (str, optional): The test case ID to include in the output filename
            
        Returns:
            dict: Validation results
        """
        print(f"🔍 Validating integration for generated files...")
        
        # Run the integration validation using LangChain agents
        validation_result = run_integration_validation(
            self.pages_dir,
            self.tests_dir,
            self.agents  # Pass LangChain agents
        )
        
        # If validation was successful, print a summary
        if validation_result["status"] == "success":
            print(f"✅ Integration validation complete")
            print(f"📝 Full critique saved to: {validation_result['critique_file']}")
            
            # Print a brief summary of the critique
            critique = validation_result["critique"]
            print("\nSummary of key findings:")
            
            # Extract section headers for a brief summary
            sections = re.findall(r'## ([^\n]+)', critique)
            for section in sections:
                print(f"- {section}")
                
            print("\nReview the full critique file for details.")
        else:
            print(f"❌ Integration validation failed: {validation_result['message']}")
        
        return validation_result
    
    def improve_from_critique(self, critique_file=None):
        """
        Improve generated files based on the integration critique.
        
        Args:
            critique_file (str, optional): Path to critique file - will use the default if not specified
            
        Returns:
            dict: Results of the improvement process
        """
        # If no critique file specified, use default
        if not critique_file:
            critique_file = os.path.join(os.path.dirname(self.pages_dir), "integration_critique.md")
        
        if not os.path.exists(critique_file):
            print(f"❌ Critique file not found: {critique_file}")
            return {"status": "error", "message": "Critique file not found"}
        
        print(f"🔍 Analyzing critique and generating improvements: {critique_file}")
        
        # Apply improvements based on the critique using LangChain agents
        result = apply_critique_improvements(
            critique_file,
            self.pages_dir,
            self.tests_dir,
            self.agents  # Pass LangChain agents
        )
        
        if result["status"] == "success":
            print("✅ Successfully improved files based on critique")
            print(f"📝 Addressed {len(result['key_issues'])} key issues:")
            
            for i, issue in enumerate(result['key_issues'], 1):
                print(f"  {i}. {issue['type']}")
            
            print(f"💾 Updated {len(result['improved_files'])} files")
        else:
            print(f"❌ Failed to improve files: {result['message']}")
        
        return result
    
    async def generate_with_design_first(self, test_case_id, test_case, selectors):
        """
        Generate Page Object Models using a design-first approach with LangChain agents.
        
        Args:
            test_case_id (str): The test case ID
            test_case (dict): The test case data
            selectors (list): List of selector data
                
        Returns:
            bool: True if successful, False otherwise
        """
        print(f"🚀 Generating with design-first approach for {test_case_id}")
        
        try:
            # Phase 1: Generate and critique design
            print("🔍 Phase 1: Generating and reviewing design")
            design = self._generate_design(test_case_id, test_case, selectors)
            critique = self._critique_design(design)
            
            # Phase 2: Generate implementation based on design and critique
            print("🔍 Phase 2: Generating implementation with design guidance")
            implementation = self._generate_implementation(design, critique, test_case_id, selectors)
            
            # Save the implementation
            page_objects = implementation.get("page_objects", [])
            test_script = implementation.get("test_script", "")
            
            if page_objects and test_script:
                self._save_results(test_case_id, page_objects, test_script)
                return True
            else:
                print("❌ Failed to generate complete implementation")
                return False
            
        except Exception as e:
            print(f"❌ Error in design-first generation: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def _generate_design(self, test_case_id, test_case, selectors):
        """Generate a high-level design for the Page Objects and test script using LangChain."""
        # Prepare selectors data for the prompt
        selectors_json = json.dumps(selectors, indent=2)
        
        # Load prompt from template file
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "prompts", 
            "design_prompt.txt"
        )
        
        # Load and format the template
        design_prompt = load_prompt_template(
            template_path,
            test_case_id=test_case_id,
            test_case_title=test_case.get('title', ''),
            test_case_steps=test_case.get('steps', ''),
            test_case_expected_results=test_case.get('expectedResults', ''),
            selectors_json=selectors_json
        )
        
        # Generate the design using LangChain agent
        design = self.agents["pom_generator"](design_prompt)
        return design

    def _critique_design(self, design):
        """Have the critique agent review the design for potential issues using LangChain."""
        # Load prompt from template file
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "prompts", 
            "critique_design_prompt.txt"
        )
        
        # Load and format the template
        critique_prompt = load_prompt_template(
            template_path,
            design=design
        )
        
        # Generate the critique using LangChain agent
        critique = self.agents["integration_critic"](critique_prompt)
        return critique

    def _generate_implementation(self, design, critique, test_case_id, selectors):
        """Generate the actual implementation based on the design and critique using LangChain."""
        # Prepare selectors data for the prompt
        selectors_json = json.dumps(selectors, indent=2)
        
        # Load prompt from template file
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "prompts", 
            "implementation_prompt.txt"
        )
        
        # Load and format the template
        implementation_prompt = load_prompt_template(
            template_path,
            design=design,
            critique=critique,
            test_case_id=test_case_id,
            selectors_json=selectors_json
        )
        
        # Generate the implementation using LangChain agent
        response = self.agents["pom_generator"](implementation_prompt)
        
        # Save debug output
        with open(f"debug_{test_case_id}_implementation.txt", "w", encoding="utf-8") as f:
            f.write(response)
        print(f"Debug: Saved response to debug_{test_case_id}_implementation.txt")
        
        # Better extraction for files
        page_objects = []
        test_script = ""
        
        # Use regular expressions to find files and their content
        file_pattern = r'###\s+([\w\.]+\.js)\s*```javascript\s*(.*?)\s*```'
        file_matches = re.findall(file_pattern, response, re.DOTALL)

        for filename, content in file_matches:
            content = content.strip()
            print(f"Found file: {filename}")
            
            # Determine if this is a page object or test script
            if 'test' in filename.lower() or 'spec' in filename.lower():
                test_script = content
                print(f"Extracted test script: {filename}")
            else:
                page_objects.append(content)
                print(f"Extracted page object: {filename}")

        print(f"Extracted {len(page_objects)} page objects and {'a' if test_script else 'no'} test script")
        
        return {
            "page_objects": page_objects,
            "test_script": test_script,
            "response": response
        }