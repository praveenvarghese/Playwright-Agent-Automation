"""
Integration validation module for Playwright test generation.
This module provides functionality to validate the integration between
Page Objects and Test Scripts using LangChain agents.
"""

import os
import json

def run_integration_validation(pages_dir, tests_dir, agents):
    """
    Run integration validation on the generated files using LangChain agents.
    
    Args:
        pages_dir (str): Directory containing page object files
        tests_dir (str): Directory containing test script files
        agents (dict): Dictionary of LangChain agent functions
        
    Returns:
        dict: Validation results
    """
    print("🔍 Running integration validation...")
    
    # Collect all generated files
    page_objects = _load_files_from_directory(pages_dir)
    test_scripts = _load_files_from_directory(tests_dir)
    
    if not page_objects or not test_scripts:
        print("⚠️ No files found for validation")
        return {"status": "error", "message": "No files found for validation"}
    
    # Prepare the prompt for the integration critic
    validation_prompt = _prepare_validation_prompt(page_objects, test_scripts)
    
    # Get the integration critic agent
    critic = agents.get("integration_critic")
    
    if not critic:
        print("⚠️ No integration_critic agent found")
        return {"status": "error", "message": "No integration_critic agent found"}
    
    # Run the validation through the critic agent (LangChain direct call)
    try:
        print("🤖 Consulting the Integration Critic...")
        
        # Direct LangChain agent call (no conversation management needed)
        critique = critic(validation_prompt)
        
        # Save the critique to a file
        critique_file = os.path.join(os.path.dirname(pages_dir), "integration_critique.md")
        with open(critique_file, "w", encoding="utf-8") as f:
            f.write(critique)
        
        print(f"✅ Integration validation complete. Results saved to {critique_file}")
        return {
            "status": "success",
            "critique": critique,
            "critique_file": critique_file
        }
        
    except Exception as e:
        print(f"❌ Error in integration validation: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Validation error: {str(e)}"
        }

def _load_files_from_directory(directory):
    """Load all JavaScript files from a directory."""
    files = {}
    if not os.path.exists(directory):
        return files
        
    for filename in os.listdir(directory):
        if filename.endswith(".js"):
            file_path = os.path.join(directory, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                files[filename] = content
    
    return files

def _prepare_validation_prompt(page_objects, test_scripts):
    """Prepare the prompt for the integration critic."""
    prompt = """
Please analyze these generated Playwright test files for cross-file issues and integration concerns.

# Page Objects
"""
    
    for filename, content in page_objects.items():
        prompt += f"\n## {filename}\n```javascript\n{content}\n```\n"
    
    prompt += "\n# Test Scripts\n"
    
    for filename, content in test_scripts.items():
        prompt += f"\n## {filename}\n```javascript\n{content}\n```\n"
    
    prompt += """
Please provide a comprehensive integration critique focusing on:
1. Dependency structures and potential circular dependencies
2. Consistency in selector strategies, error handling, and method patterns
3. Architecture coherence and code duplication
4. Configuration management and test usage patterns

Identify specific issues with examples and provide concrete recommendations for improvement.
"""
    
    return prompt