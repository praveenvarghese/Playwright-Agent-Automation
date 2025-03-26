"""
Critic agent for reviewing and improving Playwright test scripts.
This module handles interactions with the AI for reviewing code.
"""

import os
from .prompts import _load_prompt_template
from .utils import format_console_output


async def review_test_script(test_case, script_content):
    """
    Review a generated test script using AI.
    
    Args:
        test_case (dict): The test case data
        script_content (str): The generated script content
        
    Returns:
        dict: Analysis results with suggested improvements
    """
    from config.config import TestCaseCritic
    
    # Get the prompt template
    template = _load_prompt_template("script_critic.txt")
    
    # Extract test case information
    test_case_id = test_case.get('id', 'unknown')
    test_case_title = test_case.get('title', 'Unknown Test Case')
    test_case_steps = test_case.get('steps', 'No steps available')
    test_case_expected_results = test_case.get('expectedResults', 'No expected results available')
    
    # Format the prompt
    prompt = template.format(
        test_case_id=test_case_id,
        test_case_title=test_case_title,
        test_case_steps=test_case_steps,
        test_case_expected_results=test_case_expected_results,
        script_content=script_content
    )
    
    # Send to AI
    print(format_console_output("info", f"Reviewing test script for: {test_case_id}"))
    
    try:
        response = await TestCaseCritic.a_generate_reply(
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the response to extract sections
        import re
        
        # Extract revised script
        revised_script_match = re.search(r'```(?:javascript)?\s*([\s\S]*?)\s*```', response)
        revised_script = revised_script_match.group(1).strip() if revised_script_match else None
        
        # Extract issues and improvements
        issues = []
        improvements = []
        
        issues_match = re.search(r'Issues[:\n]+([\s\S]+?)(?=\n\d+\.|\Z)', response)
        if issues_match:
            issues_text = issues_match.group(1).strip()
            issues = [issue.strip() for issue in issues_text.split('\n-') if issue.strip()]
        
        improvements_match = re.search(r'Suggested Improvements[:\n]+([\s\S]+?)(?=\n\d+\.|\Z)', response)
        if improvements_match:
            improvements_text = improvements_match.group(1).strip()
            improvements = [imp.strip() for imp in improvements_text.split('\n-') if imp.strip()]
        
        # Prepare result
        result = {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "improvements": improvements,
            "revised_script": revised_script or script_content,
            "original_script": script_content
        }
        
        print(format_console_output("success", f"Review completed for {test_case_id} with {len(issues)} issues found"))
        return result
        
    except Exception as e:
        print(format_console_output("error", f"Error reviewing script: {str(e)}"))
        return {
            "has_issues": False,
            "issues": ["Error during review process"],
            "improvements": [],
            "revised_script": script_content,
            "original_script": script_content
        }


async def improve_script(test_case, script_content):
    """
    Send a script for review and return the improved version.
    
    Args:
        test_case (dict): The test case data
        script_content (str): The generated script content
        
    Returns:
        str: Improved script content
    """
    # Review the script
    review_result = await review_test_script(test_case, script_content)
    
    # Check if there are issues
    if review_result["has_issues"]:
        print(format_console_output("info", f"Issues found, using revised script for {test_case.get('id')}"))
        
        # Save the issues and improvements to a log file
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"critique_{test_case.get('id')}.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"SCRIPT CRITIQUE FOR: {test_case.get('id')}\n\n")
            
            f.write("ISSUES:\n")
            for issue in review_result["issues"]:
                f.write(f"- {issue}\n")
            
            f.write("\nIMPROVEMENTS:\n")
            for improvement in review_result["improvements"]:
                f.write(f"- {improvement}\n")
            
            f.write("\nORIGINAL SCRIPT:\n")
            f.write(review_result["original_script"])
            
            f.write("\n\nREVISED SCRIPT:\n")
            f.write(review_result["revised_script"])
        
        return review_result["revised_script"]
    else:
        print(format_console_output("info", f"No issues found in script for {test_case.get('id')}"))
        return script_content