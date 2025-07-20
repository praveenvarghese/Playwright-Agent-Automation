"""
Agent orchestrator for AI-enhanced Playwright test generation.
CLEANED: Removed unused methods, kept only working functionality.
"""

import os
from playwright_generation.agents.agent_config import create_agents
from playwright_generation.generators.pom_generation import save_page_objects
from playwright_generation.common.utils import save_file
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
        
        # Use the working LangGraph workflow
        return await generate_with_specialized_agents(
            None,  # Don't pass agents, let it create its own
            test_case_id, 
            test_case, 
            selectors, 
            lambda tc_id, page_objects, test_script: self._save_results(tc_id, page_objects, test_script),
            self.pages_dir, 
            self.tests_dir
        )
        
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