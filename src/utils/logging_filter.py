"""
This module configures logging to filter out unnecessary output from libraries
and keep the console clean.
"""
import os
import logging
from datetime import datetime

# Define constants
LOGS_DIR = "logs"  # This is relative to the project root

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
        "azure_openai_monitoring",  # This line might be creating the empty file
        "browser_use",
        "urllib3.connectionpool",
        "autogen"
    ]
    
    for noisy_logger_name in noisy_loggers:
        # Get the logger
        noisy_logger = logging.getLogger(noisy_logger_name)
        
        # Set level to ERROR for console (don't log anything below ERROR level)
        noisy_logger.setLevel(logging.ERROR)
        
        # REMOVED: We don't create separate log files for each noisy logger anymore
        # This was likely creating the empty openai_usage.log file
        
        # Prevent propagation to root logger to stop messages from appearing
        noisy_logger.propagate = False
    
    return debug_log_path