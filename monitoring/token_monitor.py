import os
import json
import time
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv
import tiktoken

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("openai_usage.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("azure_openai_monitoring")

class TokenMonitor:
    def __init__(self):
        """Initialize the token monitor with pricing and model information."""
        load_dotenv()
        
        # Pricing per 1K tokens - adjust these values based on your Azure pricing
        self.pricing = {
            "embedding": float(os.getenv("AZURE_OPENAI_EMBEDDING_PRICE_PER_1K", "0.0001")),
            "completion": float(os.getenv("AZURE_OPENAI_COMPLETION_PRICE_PER_1K", "0.002")),
            "chat_completion": float(os.getenv("AZURE_OPENAI_CHAT_COMPLETION_PRICE_PER_1K", "0.002")),
        }
        
        # Default model for token counting if not specified
        self.default_embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
        self.default_completion_model = os.getenv("AZURE_OPENAI_COMPLETION_MODEL", "gpt-35-turbo")
        
        # Initialize usage statistics
        self.monthly_usage = self._load_monthly_usage()
        self.session_usage = {
            "embedding_tokens": 0,
            "completion_tokens_input": 0,
            "completion_tokens_output": 0,
            "estimated_cost": 0.0,
            "api_calls": 0,
            "start_time": datetime.now(timezone.utc).isoformat()
        }
    
    def _load_monthly_usage(self):
        """Load monthly usage data from file if it exists."""
        try:
            current_month = datetime.now().strftime("%Y-%m")
            filename = f"usage_stats_{current_month}.json"
            
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    return json.load(f)
            else:
                return {
                    "month": current_month,
                    "embedding_tokens": 0,
                    "completion_tokens_input": 0,
                    "completion_tokens_output": 0,
                    "estimated_cost": 0.0,
                    "api_calls": 0
                }
        except Exception as e:
            logger.error(f"Error loading monthly usage data: {str(e)}")
            # Return a new empty usage record if loading fails
            return {
                "month": datetime.now().strftime("%Y-%m"),
                "embedding_tokens": 0,
                "completion_tokens_input": 0,
                "completion_tokens_output": 0,
                "estimated_cost": 0.0,
                "api_calls": 0
            }
    
    def _save_monthly_usage(self):
        """Save current monthly usage data to file."""
        try:
            current_month = datetime.now().strftime("%Y-%m")
            filename = f"usage_stats_{current_month}.json"
            
            with open(filename, "w") as f:
                json.dump(self.monthly_usage, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving monthly usage data: {str(e)}")
    
    def get_token_count(self, text, model=None):
        """
        Count tokens in text using tiktoken.
        
        Args:
            text (str): The text to count tokens for
            model (str, optional): Model name to use for token counting
            
        Returns:
            int: Number of tokens
        """
        try:
            if model is None:
                # Use default model for encoding
                model = self.default_completion_model
            
            # Get the encoding for the model
            enc = tiktoken.encoding_for_model(model)
            tokens = len(enc.encode(text))
            return tokens
        except Exception as e:
            logger.warning(f"Error counting tokens, using character-based estimate instead: {str(e)}")
            # Fallback: rough estimate based on characters (4 chars ≈ 1 token)
            return len(text) // 4
    
    def log_embedding_usage(self, text_length, token_count=None, model=None):
        """
        Log embedding API call usage.
        
        Args:
            text_length (int): Length of the text being embedded
            token_count (int, optional): Number of tokens (if already known)
            model (str, optional): Model name used for embedding
        """
        if token_count is None:
            # Estimate token count if not provided
            token_count = self.get_token_count(text_length * " ", model or self.default_embedding_model)
        
        # Calculate cost
        cost = (token_count / 1000) * self.pricing["embedding"]
        
        # Update session usage
        self.session_usage["embedding_tokens"] += token_count
        self.session_usage["estimated_cost"] += cost
        self.session_usage["api_calls"] += 1
        
        # Update monthly usage
        self.monthly_usage["embedding_tokens"] += token_count
        self.monthly_usage["estimated_cost"] += cost
        self.monthly_usage["api_calls"] += 1
        
        # Log the usage
        logger.info(f"Embedding usage: {token_count} tokens, estimated cost: ${cost:.6f}")
        
        # Save updated monthly usage
        self._save_monthly_usage()
    
    def log_completion_usage(self, prompt_tokens, completion_tokens, model=None):
        """
        Log completion API call usage.
        
        Args:
            prompt_tokens (int): Number of tokens in the prompt
            completion_tokens (int): Number of tokens in the completion
            model (str, optional): Model name used for completion
        """
        # Calculate cost
        input_cost = (prompt_tokens / 1000) * float(os.getenv("AZURE_OPENAI_COMPLETION_PRICE_PER_1K", "0.00015"))
        output_cost = (completion_tokens / 1000) * float(os.getenv("AZURE_OPENAI_CHAT_COMPLETION_PRICE_PER_1K", "0.00060"))
        total_cost = input_cost + output_cost
        
        # Update session usage
        self.session_usage["completion_tokens_input"] += prompt_tokens
        self.session_usage["completion_tokens_output"] += completion_tokens
        self.session_usage["estimated_cost"] += total_cost
        self.session_usage["api_calls"] += 1
        
        # Update monthly usage
        self.monthly_usage["completion_tokens_input"] += prompt_tokens
        self.monthly_usage["completion_tokens_output"] += completion_tokens
        self.monthly_usage["estimated_cost"] += total_cost
        self.monthly_usage["api_calls"] += 1
        
        # Log the usage
        logger.info(f"Completion usage: {prompt_tokens} prompt tokens, {completion_tokens} completion tokens, estimated cost: ${total_cost:.6f}")
        
        # Save updated monthly usage
        self._save_monthly_usage()
    
    def get_usage_report(self, include_session=True):
        """
        Get a usage report including monthly and optionally session statistics.
        
        Args:
            include_session (bool): Whether to include session statistics
            
        Returns:
            dict: Usage report
        """
        report = {
            "monthly": self.monthly_usage,
        }
        
        if include_session:
            # Update session end time
            self.session_usage["end_time"] = datetime.now(timezone.utc).isoformat()
            # Calculate session duration
            start_time = datetime.fromisoformat(self.session_usage["start_time"])
            end_time = datetime.fromisoformat(self.session_usage["end_time"])
            duration_seconds = (end_time - start_time).total_seconds()
            
            # Add session data with duration
            report["session"] = {
                **self.session_usage,
                "duration_seconds": duration_seconds
            }
        
        return report
    
    def print_usage_report(self):
        """Print a formatted usage report to the console."""
        report = self.get_usage_report()
        
        print("\n===== Azure OpenAI Usage Report =====")
        print("\nMonthly Usage:")
        print(f"Month: {report['monthly']['month']}")
        print(f"Embedding Tokens: {report['monthly']['embedding_tokens']:,}")
        print(f"Completion Input Tokens: {report['monthly']['completion_tokens_input']:,}")
        print(f"Completion Output Tokens: {report['monthly']['completion_tokens_output']:,}")
        print(f"Total API Calls: {report['monthly']['api_calls']:,}")
        print(f"Estimated Cost: ${report['monthly']['estimated_cost']:.4f}")
        
        if "session" in report:
            print("\nCurrent Session:")
            duration = report["session"]["duration_seconds"]
            duration_str = f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m {int(duration % 60)}s"
            print(f"Duration: {duration_str}")
            print(f"Embedding Tokens: {report['session']['embedding_tokens']:,}")
            print(f"Completion Input Tokens: {report['session']['completion_tokens_input']:,}")
            print(f"Completion Output Tokens: {report['session']['completion_tokens_output']:,}")
            print(f"Total API Calls: {report['session']['api_calls']:,}")
            print(f"Estimated Cost: ${report['session']['estimated_cost']:.4f}")
        
        print("\n=====================================\n")


# Create a global instance
token_monitor = TokenMonitor()

# Example usage
if __name__ == "__main__":
    # Example tracking
    text = "This is an example text to count tokens."
    tokens = token_monitor.get_token_count(text)
    print(f"Text: '{text}'")
    print(f"Token count: {tokens}")
    
    # Log some example usage
    token_monitor.log_embedding_usage(len(text), tokens)
    token_monitor.log_completion_usage(10, 50)
    
    # Print report
    token_monitor.print_usage_report()