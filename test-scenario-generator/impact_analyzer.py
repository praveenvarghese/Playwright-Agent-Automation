# impact_analyzer.py
import os
from config import config_list
import autogen
from document_retrieval import retrieve_application_context

# Define the agent to analyze impact areas
ImpactAnalysisAgent = autogen.AssistantAgent(
    name="Impact_Analyzer",
    llm_config={"config_list": config_list}
)

def load_prompt(prompt_filename):
    """
    Load the prompt from the given file in the prompts directory.
    """
    prompts_folder_path = os.path.join(os.path.dirname(__file__), "prompts")
    with open(os.path.join(prompts_folder_path, prompt_filename), "r", encoding="utf-8") as f:
        return f.read()

def analyze_feature_impact(requirement_text, top_k=8):
    """
    Analyze potential impact areas of a new feature based on the requirement text.
    
    Args:
        requirement_text (str): The requirement text to analyze
        top_k (int): Number of relevant documents to retrieve for context
        
    Returns:
        str: Impact analysis report
    """
    # Try to retrieve relevant application context
    try:
        application_context = retrieve_application_context(requirement_text, top_k=top_k)
        context_available = True
    except Exception as e:
        print(f"Warning: Could not retrieve application context: {e}")
        application_context = ""
        context_available = False
    
    # Load the prompt for ImpactAnalysisAgent
    prompt = load_prompt("impact_analysis_prompt.txt")
    
    # Format the prompt with requirement text and application context
    prompt = prompt.format(
        requirement_text=requirement_text,
        application_context=application_context
    )

    # Generate impact analysis
    response = ImpactAnalysisAgent.generate_reply(messages=[{"role": "user", "content": prompt}])
    impact_analysis = response.strip()

    # Remove 'TERMINATE' from the generated content if present
    if "TERMINATE" in impact_analysis:
        impact_analysis = impact_analysis.replace("TERMINATE", "").strip()
    
    # Log whether context was used
    if context_available:
        print("📚 Impact analysis generated with application context")
    else:
        print("⚠️ Impact analysis generated without application context")

    return impact_analysis

def critique_impact_analysis(impact_analysis):
    """
    Critique the generated impact analysis to identify areas for improvement.
    
    Args:
        impact_analysis (str): The generated impact analysis
        
    Returns:
        str: Critique feedback
    """
    # Load the critique prompt
    prompt = load_prompt("impact_analysis_critique.txt")
    prompt = prompt.format(generated_impact_analysis=impact_analysis)
    
    # Generate critique
    response = ImpactAnalysisAgent.generate_reply(messages=[{"role": "user", "content": prompt}])
    critique_feedback = response.strip()
    
    # Remove 'TERMINATE' if present
    if "TERMINATE" in critique_feedback:
        critique_feedback = critique_feedback.replace("TERMINATE", "").strip()
    
    return critique_feedback

def refine_impact_analysis(requirement_text, initial_analysis, critique_feedback, top_k=8):
    """
    Refine the impact analysis based on critique feedback.
    
    Args:
        requirement_text (str): The original requirement text
        initial_analysis (str): The initial impact analysis
        critique_feedback (str): Critique of the initial analysis
        top_k (int): Number of relevant documents to retrieve
        
    Returns:
        str: Refined impact analysis
    """
    # Retrieve application context again (may get different results with different top_k)
    try:
        application_context = retrieve_application_context(requirement_text, top_k=top_k)
    except Exception as e:
        print(f"Warning: Could not retrieve application context: {e}")
        application_context = ""
    
    # Create a refinement prompt that includes the original requirement, context, initial analysis, and critique
    refinement_prompt = f"""
Refine the following impact analysis based on the critique provided.

Requirement:
{requirement_text}

Application Context:
{application_context}

Initial Impact Analysis:
{initial_analysis}

Critique Feedback:
{critique_feedback}

Please create an improved impact analysis that addresses the issues identified in the critique.
Focus on being more specific about technical integration points and dependency chains between components.
Identify concrete testing approaches for each potential impact area.
"""
    
    # Generate refined analysis
    response = ImpactAnalysisAgent.generate_reply(messages=[{"role": "user", "content": refinement_prompt}])
    refined_analysis = response.strip()
    
    # Remove 'TERMINATE' if present
    if "TERMINATE" in refined_analysis:
        refined_analysis = refined_analysis.replace("TERMINATE", "").strip()
    
    return refined_analysis