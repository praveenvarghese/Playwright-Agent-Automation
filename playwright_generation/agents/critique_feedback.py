"""
Critique feedback loop module for improving Playwright test code based on integration critique.
This module handles extracting key issues from the critique and sending them back to the
generation agents for improvements using LangChain agents.
"""

import os
import re
import json

def apply_critique_improvements(critique_file, pages_dir, tests_dir, agents):
    """
    Apply improvements based on the integration critique using LangChain agents.
    
    Args:
        critique_file (str): Path to the integration critique file
        pages_dir (str): Directory containing page object files
        tests_dir (str): Directory containing test script files
        agents (dict): Dictionary of LangChain agent functions
        
    Returns:
        dict: Results of the improvement process
    """
    print("🔍 Analyzing critique for improvement opportunities...")
    
    try:
        # Read the critique file
        with open(critique_file, "r", encoding="utf-8") as f:
            critique_content = f.read()
        
        # Extract key issues from the critique
        key_issues = extract_key_issues(critique_content)
        
        if not key_issues:
            print("⚠️ No key issues found in the critique")
            return {"status": "warning", "message": "No key issues found for improvement"}
        
        print(f"✅ Extracted {len(key_issues)} key issues to address")
        
        # Load the original files
        page_objects = _load_files_from_directory(pages_dir)
        test_scripts = _load_files_from_directory(tests_dir)
        
        if not page_objects or not test_scripts:
            print("⚠️ Could not load original files")
            return {"status": "error", "message": "Failed to load original files"}
            
        # Group files by type for easier processing
        original_files = {
            "page_objects": page_objects,
            "test_scripts": test_scripts
        }
        
        # Prepare the improvement prompt
        improvement_prompt = _prepare_improvement_prompt(original_files, key_issues)
        
        # Get the appropriate LangChain agent
        generator = agents.get("pom_generator")
        
        if not generator:
            print("⚠️ No suitable generator agent found")
            return {"status": "error", "message": "No suitable generator agent found"}
        
        # Send the improvement request to the generator (LangChain direct call)
        print("🤖 Requesting code improvements from generator...")
        
        # Direct LangChain agent call (no conversation management)
        improved_code = generator(improvement_prompt)
        
        # Save the improved files
        print("💾 Saving improved files...")
        save_results = _save_improved_files(improved_code, pages_dir, tests_dir)
        
        if save_results["status"] == "success":
            print(f"✅ Successfully saved {save_results['count']} improved files")
        else:
            print(f"⚠️ Issues saving improved files: {save_results['message']}")
        
        return {
            "status": "success",
            "key_issues": key_issues,
            "improved_files": save_results["files"],
            "improvement_response": improved_code
        }
        
    except Exception as e:
        print(f"❌ Error in critique improvement process: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Improvement process error: {str(e)}"
        }

def extract_key_issues(critique_content):
    """Extract key issues from the critique content."""
    key_issues = []
    
    # Extract the Critical Issues section
    critical_section_match = re.search(r'## Critical Issues\s+(.+?)(?:##|\Z)', 
                                     critique_content, re.DOTALL)
    
    if not critical_section_match:
        return key_issues
        
    critical_section = critical_section_match.group(1)
    
    # Find all main issue types (numbered items with bold titles)
    main_issues = re.findall(r'\d+\.\s+\*\*([^*]+)\*\*', critical_section)
    
    # For each main issue, find the sub-issues (bulleted items)
    for issue_type in main_issues:
        # Find the section for this issue type
        issue_section_pattern = rf'\d+\.\s+\*\*{re.escape(issue_type)}\*\*\s+(.*?)(?=\d+\.\s+\*\*|\Z)'
        issue_section_match = re.search(issue_section_pattern, critical_section, re.DOTALL)
        
        if issue_section_match:
            issue_section = issue_section_match.group(1)
            
            # Find all sub-issues (bulleted items with bold titles)
            sub_issues = re.findall(r'-\s+\*\*([^*]+)\*\*:\s+(.+?)(?=-\s+\*\*|\Z)', issue_section, re.DOTALL)
            
            for sub_issue_type, description in sub_issues:
                key_issues.append({
                    "type": f"{issue_type} - {sub_issue_type.strip()}",
                    "description": description.strip(),
                    "recommendation": "",  # Find recommendations separately
                    "priority": 1  # Set default priority
                })
    
    # Find recommendations for key issues
    recommendations_match = re.search(r'## Recommendations\s+(.+?)(?:##|\Z)', 
                                    critique_content, re.DOTALL)
    
    if recommendations_match:
        recommendations_section = recommendations_match.group(1)
        recommendation_items = re.findall(r'\d+\.\s+\*\*([^*]+)\*\*\s+(.+?)(?=\d+\.\s+\*\*|\Z)', 
                                        recommendations_section, re.DOTALL)
        
        # Match recommendations to issues
        for rec_type, rec_content in recommendation_items:
            rec_type = rec_type.strip()
            
            # Find matching issues
            for issue in key_issues:
                if rec_type in issue["type"]:
                    issue["recommendation"] = rec_content.strip()
                    issue["priority"] += 1  # Increase priority if recommendation exists
    
    # Sort by priority and take top 5
    key_issues.sort(key=lambda x: x["priority"], reverse=True)
    return key_issues[:5]

def _prepare_improvement_prompt(original_files, key_issues):
    """
    Prepare the prompt for requesting improvements.
    
    Args:
        original_files (dict): Dictionary of original files by type
        key_issues (list): List of key issues to address
        
    Returns:
        str: Formatted prompt for the generator
    """
    prompt = """
You are tasked with improving the following Playwright test files based on specific issues identified by an Integration Critic.

# Original Files

## Page Objects
"""
    
    # Add page objects
    for filename, content in original_files["page_objects"].items():
        prompt += f"\n### {filename}\n```javascript\n{content}\n```\n"
    
    prompt += "\n## Test Scripts\n"
    
    # Add test scripts
    for filename, content in original_files["test_scripts"].items():
        prompt += f"\n### {filename}\n```javascript\n{content}\n```\n"
    
    prompt += "\n# Key Issues to Address\n"
    
    # Add key issues
    for i, issue in enumerate(key_issues, 1):
        prompt += f"\n## Issue {i}: {issue['type']}\n"
        prompt += f"{issue['description']}\n"
        
        if issue["recommendation"]:
            prompt += f"\n**Recommendation**: {issue['recommendation']}\n"
    
    prompt += """
# Your Task
Please provide improved versions of ALL the original files that address the key issues identified above.

Important guidelines:
1. Maintain the same functionality as the original files
2. Address all the identified issues
3. Keep the same file structure (BasePage, LoginPage, EnvironmentPage, test script)
4. Implement the recommendations for each issue
5. Format your response with clear file headers and the complete file content for each file

Format each file as:
### FileName.js
```javascript
// Complete improved file content
```

Ensure ALL files are included in your response, not just the ones that were changed.
"""
    
    return prompt

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

def _save_improved_files(improvement_response, pages_dir, tests_dir):
    """
    Extract and save the improved files from the response.
    
    Args:
        improvement_response (str): Response from the generator agent
        pages_dir (str): Directory to save page objects
        tests_dir (str): Directory to save test scripts
        
    Returns:
        dict: Result of the save operation
    """
    try:
        # Extract file blocks
        file_pattern = r'###\s+(\w+\.js)\s+```javascript\s+(.*?)```'
        file_matches = re.findall(file_pattern, improvement_response, re.DOTALL)
        
        if not file_matches:
            return {
                "status": "error",
                "message": "No improved files found in response",
                "files": [],
                "count": 0
            }
        
        saved_files = []
        
        # Create backup directory
        import time
        backup_dir = os.path.join(os.path.dirname(pages_dir), "backups", 
                                   f"backup_{int(time.time())}")
        os.makedirs(backup_dir, exist_ok=True)
        
        # For each file
        for filename, content in file_matches:
            content = content.strip()
            
            # Determine the directory
            if "Page" in filename or filename == "BasePage.js":
                target_dir = pages_dir
            else:
                target_dir = tests_dir
            
            # Create a backup
            original_path = os.path.join(target_dir, filename)
            if os.path.exists(original_path):
                backup_path = os.path.join(backup_dir, filename)
                with open(original_path, "r", encoding="utf-8") as src:
                    with open(backup_path, "w", encoding="utf-8") as dst:
                        dst.write(src.read())
            
            # Save the improved file
            file_path = os.path.join(target_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            saved_files.append(file_path)
        
        return {
            "status": "success",
            "message": f"Saved {len(saved_files)} improved files",
            "files": saved_files,
            "count": len(saved_files)
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error saving improved files: {str(e)}",
            "files": [],
            "count": 0
        }