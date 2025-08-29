"""
This module provides logging utilities and console output filtering.
"""
import os
import logging
from datetime import datetime

# Define log directory
LOGS_DIR = "logs"  # This is relative to the project root

def setup_logging():
    """Set up basic logging configuration."""
    # Create logs directory if it doesn't exist
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
        print(f"Created log directory: {LOGS_DIR}")
    
    # Configure root logger to write to file
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(LOGS_DIR, f"application_{timestamp}.log")
    
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
    token_handler = logging.FileHandler(os.path.join(LOGS_DIR, f"token_usage_{timestamp}.log"))
    token_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    loggers['token'].addHandler(token_handler)
    loggers['token'].propagate = False  # Don't propagate to root logger
    
    # Configure API call logger
    api_handler = logging.FileHandler(os.path.join(LOGS_DIR, f"api_calls_{timestamp}.log"))
    api_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    loggers['api'].addHandler(api_handler)
    loggers['api'].propagate = False
    
    # Configure error logger
    error_handler = logging.FileHandler(os.path.join(LOGS_DIR, f"errors_{timestamp}.log"))
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    loggers['error'].addHandler(error_handler)
    
    return loggers

def configure_clean_console():
    """
    Configure logging to redirect all library logs to files and 
    keep only application-specific messages in the console.
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
        print(f"Created logs directory at: {os.path.abspath(LOGS_DIR)}")
    
    # Get timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d")
    
    # Configure root logger to capture everything
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create a file handler for all logs
    debug_log_path = os.path.join(LOGS_DIR, f"application_debug_{timestamp}.log")
    file_handler = logging.FileHandler(debug_log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # Add a console handler that only shows WARNING and above for most loggers
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(console_handler)
    
    # Disable console logging for specific loggers that produce a lot of output
    noisy_loggers = [
        "azure.core.pipeline.policies.http_logging_policy",
        "azure_openai_monitoring",
        "browser_use",
        "urllib3.connectionpool",
        "autogen"
    ]
    
    for noisy_logger_name in noisy_loggers:
        # Get the logger
        noisy_logger = logging.getLogger(noisy_logger_name)
        
        # Set level to ERROR for console (don't log anything below ERROR level)
        noisy_logger.setLevel(logging.ERROR)
        
        # Prevent propagation to root logger to stop messages from appearing
        noisy_logger.propagate = False
    
    return debug_log_path

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