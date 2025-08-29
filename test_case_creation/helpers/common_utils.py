import numpy as np

# Printing utility functions
def print_progress(message): print(f"🔹 {message}")
def print_success(message): print(f"✅ {message}")
def print_warning(message): print(f"⚠️ {message}")
def print_error(message): print(f"❌ {message}")

def calculate_cosine_similarity(embedding1, embedding2):
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1 (list): First embedding vector
        embedding2 (list): Second embedding vector
        
    Returns:
        float: Cosine similarity (between 0 and 1)
    """
    # Convert to numpy arrays
    a = np.array(embedding1)
    b = np.array(embedding2)
    
    # Calculate cosine similarity
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    # Ensure the result is between 0 and 1
    return max(0.0, min(1.0, similarity))