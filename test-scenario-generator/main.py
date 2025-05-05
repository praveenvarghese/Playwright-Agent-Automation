# main.py
import os
from scenario_generation import generate_test_scenarios
from critique_handling import critique_test_scenarios
from file_operations import save_to_file, load_file

MAX_CRITIQUE_ITERATIONS = 2  # Control the number of critique iterations

def main():
    # Load requirement from input file
    script_dir = os.path.dirname(__file__)
    input_path = os.path.join(script_dir, "input_example.txt")

    requirement_text = load_file(input_path)

    # Step 1: Generate initial test scenarios
    print("🔹 Generating test scenarios...")
    generated_scenarios = generate_test_scenarios(requirement_text)

    if generated_scenarios:
        print(f"\n✅ Test Scenarios Generated:\n{generated_scenarios}")

        # Step 2: Critique the test scenarios (First critique)
        print("🔹 Sending test scenarios for critique...")
        critique_feedback = critique_test_scenarios(generated_scenarios)

        if critique_feedback:
            print(f"\n✅ Critique Feedback (1st iteration):\n{critique_feedback}")

            # Step 3: Generate new test scenarios based on critique (First round)
            print("🔹 Generating updated test scenarios based on critique...")
            updated_scenarios = generate_test_scenarios(critique_feedback)

            # Step 4: Second critique based on the updated scenarios (Second iteration)
            print("🔹 Sending updated test scenarios for second critique...")
            second_critique_feedback = critique_test_scenarios(updated_scenarios)

            if second_critique_feedback:
                print(f"\n✅ Second Critique Feedback:\n{second_critique_feedback}")

                # Step 5: Generate final test scenarios based on second critique feedback
                final_scenarios = generate_test_scenarios(second_critique_feedback)

                # Step 6: Save the final test scenarios and critique feedback to files
                save_to_file("final_generated_test_scenarios.txt", final_scenarios)
                save_to_file("final_critique_feedback.txt", second_critique_feedback)

                print(f"\n✅ Final Test Scenarios and Feedback Saved.")
            else:
                print("\n❌ No second critique feedback received.")
        else:
            print("\n❌ No critique feedback received.")
    else:
        print("\n❌ No test scenarios generated.")

if __name__ == "__main__":
    main()
