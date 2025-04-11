from core.prompt_builder import build_critique_prompt
from core.playwright_agents import PlaywrightCriticAgent

def review_script(test_case: dict, generated_script: str) -> str:
    """
    Uses LLM to review and improve a generated test script.

    Args:
        test_case (dict): The original test case
        generated_script (str): The raw script from initial generation

    Returns:
        str: The improved script (if any), otherwise original
    """
    print("🔍 Running Critique Agent...")

    # Build the critique prompt
    prompt = build_critique_prompt(test_case, generated_script)

    # Use AutoGen agent to initiate chat
    result = PlaywrightCriticAgent.initiate_chat(message=prompt)

    # Extract final script
    reviewed_script = result.summary if hasattr(result, "summary") else str(result)

    if not reviewed_script.strip():
        print("⚠️ No improved script returned. Using original.")
        return generated_script

    print("✅ Script reviewed and improved.")
    return reviewed_script
