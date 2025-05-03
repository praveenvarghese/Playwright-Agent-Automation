import json
import os
from playwright_generation.orchestration.extraction_utils import extract_page_objects_from_specialized, extract_test_script_from_specialized

async def generate_with_specialized_agents(agents, test_case_id, test_case, selectors, 
                                          save_callback, pages_dir, tests_dir):
    """
    Generate Page Object Models and test script using specialized agents.

    Args:
        agents (dict): Dictionary of agent instances
        test_case_id (str): The test case ID
        test_case (dict): The test case data
        selectors (list): List of selector data
        save_callback (function): Callback function to save results
        pages_dir (str): Directory to save page objects
        tests_dir (str): Directory to save test scripts

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\U0001f680 Generating with specialized agents for {test_case_id}")

    try:
        user_proxy = agents["user_proxy"]
        pom_generator = agents["pom_generator"]
        pom_critic = agents["pom_critic"]
        test_generator = agents["test_generator"]
        test_critic = agents["test_critic"]

        selectors_json = json.dumps(selectors, indent=2)

        # Step 1: Generate Page Objects
        pom_prompt = f"""
        Generate Page Object Models for Playwright based on the provided selectors. 

        Test Case ID: {test_case_id}
        Test Case Title: {test_case.get('title', '')}

        Selectors Data:
        ```json
        {selectors_json}
        ```

        Instructions:
        1. Analyze the selectors to identify logical pages
        2. Create a BasePage.js file with common functionality
        3. Create specific page objects for each logical page
        4. Follow Page Object Model best practices
        5. Format your response with clear file headers and JavaScript code blocks

        Format each file as:
        ### 1. FileName.js
        ```javascript
        // Implementation
        ```
        """

        print("\U0001f50d Step 1: Generating Page Object Models")
        pom_chat = user_proxy.initiate_chat(
            pom_generator,
            message=pom_prompt,
            max_turns=2
        )

        pom_response = pom_chat.chat_history[-1]["content"]

        # Step 2: Critique Page Objects
        critique_prompt = f"""
        Review these Page Object Models and suggest improvements:

        {pom_response}

        Focus on:
        1. Structure and organization
        2. Selector strategies
        3. Method design and naming
        4. Error handling
        5. Documentation

        Provide specific code examples for your suggestions.
        """

        print("\U0001f50d Step 2: Critiquing Page Object Models")
        critique_chat = user_proxy.initiate_chat(
            pom_critic,
            message=critique_prompt,
            max_turns=2
        )

        critique_response = critique_chat.chat_history[-1]["content"]

        # Step 3: Improve Page Objects based on critique
        improvement_prompt = f"""
        Improve these Page Object Models based on the critique:

        Original Page Objects:
        {pom_response}

        Critique:
        {critique_response}

        Provide the complete improved implementation following the same format:
        ### 1. FileName.js
        ```javascript
        // Implementation
        ```
        """

        print("\U0001f50d Step 3: Improving Page Object Models")
        improved_pom_chat = user_proxy.initiate_chat(
            pom_generator,
            message=improvement_prompt,
            max_turns=2
        )

        improved_pom = improved_pom_chat.chat_history[-1]["content"]

        # Extract page objects from the improved response
        page_objects = extract_page_objects_from_specialized(improved_pom)

        # Step 4: Generate Test Script
        test_case_json = json.dumps(test_case, indent=2)

        test_prompt = f"""
        Create a Playwright test script using the Page Object Models:

        {improved_pom}

        You must use the following testCase values inside your actual test code.

        ✅ Correct:
            await page.goto(testCase.loginUrl);
            await loginPage.login(testCase.username, testCase.password);
            await environmentPage.createEnvironment(testCase.environmentName);
            await expect(page.locator(testCase.resultSelector)).toHaveText(testCase.expectedText);

        ❌ Incorrect:
            await page.goto('https://example.com/login');
            await loginPage.login('admin', 'password');
            await environmentPage.createEnvironment('My New Environment');

        Test Case:
        ```json
        {test_case_json}
        ```

        Requirements:
        1. Do NOT use any hardcoded values. Use fields from `testCase` like:
           - testCase.loginUrl
           - testCase.username
           - testCase.password
           - testCase.environmentName
           - testCase.expectedText

        2. Use only the values passed in `testCase` for all navigation, inputs, and assertions.

        3. Follow best practices:
           - Arrange → Act → Assert
           - Use ES6 module imports
           - Page Objects should only encapsulate selectors and actions

        Format the output as:
        ### N. testCase.spec.js
        ```javascript
        // Implementation here
        ```
        """

        print("\U0001f50d Step 4: Generating Test Script")
        test_chat = user_proxy.initiate_chat(
            test_generator,
            message=test_prompt,
            max_turns=2
        )

        test_script = test_chat.chat_history[-1]["content"]

        # Step 5: Critique Test Script
        test_critique_prompt = f"""
        Review this test script and suggest improvements:

        {test_script}

        Focus on:
        1. Reliability and robustness
        2. Wait strategies
        3. Assertion quality
        4. Error handling
        5. Test structure

        Provide specific code examples for your suggestions.
        """

        print("\U0001f50d Step 5: Critiquing Test Script")
        test_critique_chat = user_proxy.initiate_chat(
            test_critic,
            message=test_critique_prompt,
            max_turns=2
        )

        test_critique = test_critique_chat.chat_history[-1]["content"]

        # Step 6: Improve Test Script based on critique
        test_improvement_prompt = f"""
        Improve this test script based on the critique:

        Original Test Script:
        {test_script}

        Critique:
        {test_critique}

        Provide the complete improved implementation as:
        ### N. testCase.spec.js
        ```javascript
        // Implementation
        ```
        """

        print("\U0001f50d Step 6: Improving Test Script")
        final_test_chat = user_proxy.initiate_chat(
            test_generator,
            message=test_improvement_prompt,
            max_turns=2
        )

        final_test_script = final_test_chat.chat_history[-1]["content"]

        # Extract test script from the final response
        test_file = extract_test_script_from_specialized(final_test_script)

        # Save the results using the callback
        save_callback(test_case_id, page_objects, test_file)

        print(f"✅ Successfully generated test for {test_case_id} using specialized agents")
        return True

    except Exception as e:
        print(f"❌ Error in specialized generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
