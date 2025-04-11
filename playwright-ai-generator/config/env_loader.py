import os
from dotenv import load_dotenv

# Load the .env file from the parent directory of this script
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv(dotenv_path)

def get_app_config():
    """
    Returns:
        dict: Contains application login URL, username, password, and headless mode flag.
    """
    return {
        "APP_URL": os.getenv("APP_URL"),
        "APP_USERNAME": os.getenv("APP_USERNAME"),
        "APP_PASSWORD": os.getenv("APP_PASSWORD"),
        "APP_HEADLESS": os.getenv("APP_HEADLESS", "true").lower() == "true"
    }
