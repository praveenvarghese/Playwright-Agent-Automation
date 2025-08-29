# rag_diagnostic.py
"""
A diagnostic script to test the RAG retrieval mechanism and analyze why certain 
information might not be retrieved effectively.
"""

import os
from document_retrieval import retrieve_application_context, generate_embeddings
from config import config_list
import autogen

# Test different queries to see what context they retrieve
TEST_QUERIES = [
    "App-developer controlled WebUI Menu",
    "WebUI Menu configuration",
    "Menu bar in WebUI application",
    "Control which pages appear in menu",
    "Define menu contents through model specification",
    "Menu items with hierarchical structure",
    "Menu with Name, Page URI, Parent Page URI fields",
    "Workflow feature in WebUI",
    "Application Settings for menu control"
]

def test_retrieval_for_queries():
    """
    Test retrieval for different queries and analyze the results.
    """
    print("==== TESTING RETRIEVAL WITH DIFFERENT QUERIES ====\n")
    
    results = {}
    
    for query in TEST_QUERIES:
        print(f"\n--- Testing query: '{query}' ---")
        
        try:
            # Get embeddings for the query
            query_embedding = generate_embeddings(query)
            print(f"Successfully generated embeddings for: '{query}'")
            
            # Retrieve application context with different top_k values
            for k in [3, 5, 8]:
                context = retrieve_application_context(query, top_k=k)
                
                print(f"\nResults with top_k={k}:")
                if context:
                    # Extract document IDs from the context
                    doc_ids = []
                    for line in context.split('\n'):
                        if line.startswith("Document:"):
                            doc_ids.append(line.split("Document:")[1].strip())
                    
                    doc_ids_str = ", ".join(doc_ids)
                    print(f"Retrieved {len(doc_ids)} documents: {doc_ids_str}")
                    
                    # Store the results
                    results[f"{query}_{k}"] = {
                        'doc_ids': doc_ids,
                        'context_length': len(context)
                    }
                    
                    # Print a small sample of the context for analysis
                    context_sample = context[:300] + "..." if len(context) > 300 else context
                    print(f"Sample context: {context_sample}")
                else:
                    print("No context retrieved.")
                    results[f"{query}_{k}"] = {
                        'doc_ids': [],
                        'context_length': 0
                    }
        except Exception as e:
            print(f"Error testing query '{query}': {e}")
    
    # Analyze the results
    print("\n==== ANALYSIS ====\n")
    
    # Find which queries retrieved the most documents
    best_queries = sorted(
        [(q.split('_')[0], results[q]['context_length']) for q in results if results[q]['context_length'] > 0],
        key=lambda x: x[1],
        reverse=True
    )
    
    print("Best performing queries (by context length):")
    for q, length in best_queries[:5]:
        print(f"- '{q}': {length} characters")
    
    # Find the most frequently retrieved documents
    all_docs = []
    for result in results.values():
        all_docs.extend(result['doc_ids'])
    
    doc_counts = {}
    for doc in all_docs:
        if doc in doc_counts:
            doc_counts[doc] += 1
        else:
            doc_counts[doc] = 1
    
    most_relevant_docs = sorted(
        [(doc, count) for doc, count in doc_counts.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    print("\nMost relevant documents (by retrieval frequency):")
    for doc, count in most_relevant_docs[:5]:
        print(f"- {doc}: retrieved {count} times")
    
    # Suggest best query + top_k combination
    best_combination = None
    max_docs = 0
    
    for query, k in [(q.split('_')[0], int(q.split('_')[1])) for q in results.keys()]:
        key = f"{query}_{k}"
        num_docs = len(results[key]['doc_ids'])
        if num_docs > max_docs:
            max_docs = num_docs
            best_combination = (query, k)
    
    if best_combination:
        print(f"\nBest query + top_k combination: '{best_combination[0]}' with top_k={best_combination[1]}")
        print(f"Retrieved {max_docs} documents")
    
    return results

def test_with_specific_requirement():
    """
    Test retrieval with a specific menu control requirement.
    """
    print("\n==== TESTING WITH ACTUAL MENU REQUIREMENT ====\n")
    
    requirement = """Feature: App-developer controlled WebUI Menu - Acceptance Criteria
Requirement:
Necessary to give the App developer control over which pages appear in the menu bar
Acceptance Criteria:
1. The WebUI menu contents can be defined through a model specification in the Application Settings.
2. When the option is not set, the menu bar follows the default behavior of including all pages from both MainProject and libraries.
3. The menu can be completely hidden by using an identifier with no data.
4. Each menu item in the specification includes:
   - Name field for the display text
   - Page URI field that links to an actual page
   - Parent Page URI field for creating nested menu structures
   - Tooltip field for providing additional context on hover
   - State field (Active, Inactive, or Hidden) to control display
5. Menu links only appear if the Page URI resolves to a valid page."""
    
    print(f"Testing with requirement:\n{requirement}\n")
    
    try:
        # Try with different top_k values
        for k in [3, 5, 8]:
            context = retrieve_application_context(requirement, top_k=k)
            
            print(f"\nResults with top_k={k}:")
            if context:
                # Extract document IDs from the context
                doc_ids = []
                for line in context.split('\n'):
                    if line.startswith("Document:"):
                        doc_ids.append(line.split("Document:")[1].strip())
                
                doc_ids_str = ", ".join(doc_ids)
                print(f"Retrieved {len(doc_ids)} documents: {doc_ids_str}")
                
                # Print a small sample of the context for analysis
                context_sample = context[:300] + "..." if len(context) > 300 else context
                print(f"Sample context: {context_sample}")
            else:
                print("No context retrieved.")
    except Exception as e:
        print(f"Error testing with requirement: {e}")

def simulate_test_scenario_generation():
    """
    Simulate test scenario generation with retrieved context.
    """
    print("\n==== SIMULATING TEST SCENARIO GENERATION ====\n")
    
    requirement = """Feature: App-developer controlled WebUI Menu - Acceptance Criteria
Requirement:
Necessary to give the App developer control over which pages appear in the menu bar
Acceptance Criteria:
1. The WebUI menu contents can be defined through a model specification in the Application Settings.
2. When the option is not set, the menu bar follows the default behavior of including all pages from both MainProject and libraries.
3. The menu can be completely hidden by using an identifier with no data."""
    
    try:
        # Get context with different top_k values
        for k in [3, 5, 8]:
            context = retrieve_application_context(requirement, top_k=k)
            
            if not context:
                print(f"No context retrieved with top_k={k}")
                continue
            
            print(f"\n--- Test Scenario Generation Simulation with top_k={k} ---")
            
            # Create a test agent instance
            TestScenarioAgent = autogen.AssistantAgent(
                name="TestScenario_Generator",
                llm_config={"config_list": config_list}
            )
            
            # Create the prompt
            prompt = f"""
From the requirement and acceptance criteria below, generate a list of high-level test scenarios.
Each scenario should be 1–2 sentences describing what needs to be tested.

Consider the following application context when creating test scenarios:
{context}

Requirement:
{requirement}

Important Guidelines:
1. Create specific test scenarios covering each acceptance criterion
2. Include scenarios for potential impacts on existing features
3. Make scenarios relevant to the specific application based on the context provided
4. Use specific terminology and features mentioned in the application context
5. Generate only 3-5 example scenarios to demonstrate quality
"""
            
            # Generate a sample response
            response = TestScenarioAgent.generate_reply(messages=[{"role": "user", "content": prompt}])
            
            # Print the generated scenarios
            print("\nSample Generated Test Scenarios:")
            print(response.strip())
    except Exception as e:
        print(f"Error simulating test scenario generation: {e}")

if __name__ == "__main__":
    # Run the diagnostic tests
    test_retrieval_for_queries()
    test_with_specific_requirement()
    simulate_test_scenario_generation()