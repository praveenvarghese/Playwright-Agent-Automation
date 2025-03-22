import os
import logging
from datetime import datetime

# Define log directory
LOG_DIR = "logs"

def setup_logging():
    """Set up basic logging configuration."""
    # Create logs directory if it doesn't exist
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        print(f"Created log directory: {LOG_DIR}")
    
    # Configure root logger to write to file
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(LOG_DIR, f"application_{timestamp}.log")
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Console handler
        ]
    )
    
    # Create specific loggers
    loggers = {
        'main': logging.getLogger('main'),
        'token': logging.getLogger('token'),
        'api': logging.getLogger('api'),
        'error': logging.getLogger('error')
    }
    
    # Configure token logger to write to separate file
    token_handler = logging.FileHandler(os.path.join(LOG_DIR, f"token_usage_{timestamp}.log"))
    token_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    loggers['token'].addHandler(token_handler)
    loggers['token'].propagate = False  # Don't propagate to root logger
    
    # Configure API call logger
    api_handler = logging.FileHandler(os.path.join(LOG_DIR, f"api_calls_{timestamp}.log"))
    api_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    loggers['api'].addHandler(api_handler)
    loggers['api'].propagate = False
    
    # Configure error logger
    error_handler = logging.FileHandler(os.path.join(LOG_DIR, f"errors_{timestamp}.log"))
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    loggers['error'].addHandler(error_handler)
    
    return loggers

# Helper methods for formatted console output
def success(message):
    """Format a success message."""
    return f"✅ {message}"

def progress(message):
    """Format a progress message."""
    return f"🔹 {message}"

def warning(message):
    """Format a warning message."""
    return f"⚠️ {message}"

def error(message):
    """Format an error message."""
    return f"❌ {message}"
