# file_operations.py

def save_to_file(file_name, content):
    """
    Save the given content to a file.
    """
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(content)

def load_file(file_name):
    """
    Load the content from a file.
    """
    with open(file_name, "r", encoding="utf-8") as f:
        content = f.read()
    return content
