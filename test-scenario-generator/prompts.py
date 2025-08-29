def build_test_scenario_prompt(requirement_text: str) -> str:
    return f"""
You are an AI QA assistant.

From the requirement and acceptance criteria below, generate a list of high-level test scenarios.
Each scenario should be 1–2 sentences long and describe what needs to be tested.
Do not include steps or expected results. Output only the numbered list.

{requirement_text}
"""
