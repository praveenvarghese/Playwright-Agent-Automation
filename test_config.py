"""
Test configuration and setup utilities
TOKEN OPTIMIZATION APPLIED - Production Ready
"""

import os
import json
import hashlib
import time
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TestConfig:
    """Test configuration management"""
    
    @staticmethod
    def get_browser_config():
        """Get browser configuration for clean sessions"""
        return {
            "headless": False,  # Set to True for faster execution
            "viewport": {"width": 1920, "height": 1080},
            "ignore_https_errors": True,
            "permissions": ["notifications"],
            "record_video_size": {"width": 640, "height": 480},  # Smaller videos for token efficiency
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9"
            }   
        }
    
    @staticmethod
    def get_login_config():
        """Get optimized login configuration"""
        return {
            "url": os.getenv('APP_URL'),
            "email": os.getenv('APP_EMAIL'),
            "password": os.getenv('APP_PASSWORD'),
            "login_timeout": 30,  # seconds
            "post_login_wait": 2,   # seconds to wait after login
            "token_budget": 30000   # tokens allocated for login phase
        }
    
    @staticmethod
    def validate_environment():
        """Validate required environment variables"""
        required_vars = [
            'APP_URL', 'APP_EMAIL', 'APP_PASSWORD',
            'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 
            'AZURE_OPENAI_DEPLOYMENT_NAME'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
        
        return True
    
    @staticmethod
    def get_chunking_config():
        """Get chunking configuration for large tests"""
        return {
            "max_chunk_size": int(os.getenv('MCP_CHUNK_SIZE', '20')),
            "max_tokens_per_chunk": int(os.getenv('MCP_MAX_TOKENS', '25000')),
            "enable_checkpointing": os.getenv('MCP_CHECKPOINTING', 'true').lower() == 'true',
            "external_log_retention_days": int(os.getenv('LOG_RETENTION_DAYS', '7'))
        }
    
    @staticmethod
    def create_execution_signature(test_case_id, steps_hash):
        """Create execution signature for verification"""
        signature_data = f"{test_case_id}_{steps_hash}_{int(time.time() / 3600)}"  # Hour-based
        return hashlib.sha256(signature_data.encode()).hexdigest()[:16]

class TestStepParser:
    """Parse and optimize test steps"""
    
    @staticmethod
    def parse_test_case(test_case: Dict) -> Dict:
        """Parse and optimize test case structure"""
        
        # Ensure we have structured steps
        if not test_case.get('structured_steps') and test_case.get('steps'):
            # Try to parse basic steps into structured format
            steps_text = test_case['steps']
            structured_steps = TestStepParser.convert_basic_to_structured(steps_text)
            test_case['structured_steps'] = structured_steps
        
        return test_case
    
    @staticmethod
    def convert_basic_to_structured(steps_text: str) -> List[Dict]:
        """Convert basic step text to structured format"""
        
        # Quick validation for token efficiency
        if len(steps_text) > 10000:  # ~2500 tokens
            print("⚠️  Very large step description detected, may need manual chunking")
        
        structured_steps = []
        
        # Simple parsing - split by lines and create basic structure
        lines = [line.strip() for line in steps_text.split('\n') if line.strip()]
        
        for i, line in enumerate(lines, 1):
            if line.lower().startswith(('step', str(i))):
                # Remove step number prefix
                action = line.split(':', 1)[-1].strip() if ':' in line else line
            else:
                action = line
            
            structured_steps.append({
                'step': i,
                'action': action,
                'action_hash': hashlib.md5(action.encode()).hexdigest()[:8],  # For duplicate detection
                'expected': None  # Will be filled if we can parse expectations
            })
        
        return structured_steps
    
    @staticmethod
    def create_login_steps() -> List[Dict]:
        """Create optimized login step sequence"""
        login_config = TestConfig.get_login_config()
        
        return [
            {
                'tool': 'navigate_to',
                'args': {'url': login_config['url']},
                'description': 'Navigate to login page'
            },
            {
                'tool': 'browser_snapshot',
                'args': {},
                'description': 'Capture login page state'
            },
            {
                'tool': 'type_text',
                'args': {'element': 'username', 'text': login_config['email']},
                'description': 'Enter Email'
            },
            {
                'tool': 'type_text', 
                'args': {'element': 'password', 'text': login_config['password']},
                'description': 'Enter password'
            },
            {
                'tool': 'click_element',
                'args': {'element': 'login'},
                'description': 'Click login button'
            },
            {
                'tool': 'browser_snapshot',
                'args': {},
                'description': 'Verify login success'
            }
        ]

class ExecutionMonitor:
    """Monitor test execution and detect issues"""
    
    def __init__(self):
        self.execution_stats = {
            'total_iterations': 0,
            'successful_tools': 0,
            'failed_tools': 0,
            'login_attempts': 0,
            'phases_completed': [],
            'token_usage': 0,
            'optimization_enabled': True
        }
    
    def log_iteration(self, phase: str, iteration: int, success: bool = True):
        """Log iteration details"""
        self.execution_stats['total_iterations'] += 1
        
        if success:
            self.execution_stats['successful_tools'] += 1
        else:
            self.execution_stats['failed_tools'] += 1
    
    def log_token_usage(self, estimated_tokens: int):
        """Log token usage for monitoring"""
        self.execution_stats['token_usage'] = estimated_tokens
    
    def log_phase_completion(self, phase: str, success: bool = True):
        """Log phase completion"""
        self.execution_stats['phases_completed'].append({
            'phase': phase,
            'success': success,
            'iterations': self.execution_stats['total_iterations']
        })
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary"""
        success_rate = (
            self.execution_stats['successful_tools'] / 
            max(1, self.execution_stats['total_iterations'])
        ) * 100
        
        return {
            'total_iterations': self.execution_stats['total_iterations'],
            'success_rate': f"{success_rate:.1f}%",
            'phases_completed': len(self.execution_stats['phases_completed']),
            'login_efficiency': self.execution_stats.get('login_iterations', 0),
            'token_efficiency': f"{self.execution_stats.get('token_usage', 0)} tokens used"
        }
    
    def detect_stuck_execution(self, recent_logs: List[Dict]) -> bool:
        """Detect if execution is stuck in a loop"""
        if len(recent_logs) < 5:
            return False
        
        # Check for repeated tool calls with same arguments
        recent_tools = [(log.get('tool'), str(log.get('args', {}))) for log in recent_logs[-5:]]
        
        # If same tool+args repeated 3+ times, likely stuck
        tool_counts = {}
        for tool_sig in recent_tools:
            tool_counts[tool_sig] = tool_counts.get(tool_sig, 0) + 1
        
        return max(tool_counts.values()) >= 3

# Utility functions for better error handling
def create_recovery_prompt(error_context: Dict) -> str:
    """Create recovery prompt based on error context"""
    
    base_prompt = """
The previous action encountered an issue. Let's recover:

ERROR CONTEXT:
"""
    
    if error_context.get('last_tool'):
        base_prompt += f"- Last tool: {error_context['last_tool']}\n"
    
    if error_context.get('error_message'):
        base_prompt += f"- Error: {error_context['error_message']}\n"
    
    base_prompt += """
RECOVERY ACTIONS:
1. Take a browser_snapshot to see current page state
2. Based on the snapshot, determine the correct next action
3. If on wrong page, navigate back to the correct location
4. Continue with the test steps

Focus on getting back on track efficiently."""
    
    return base_prompt

def optimize_tool_args(tool_name: str, args: Dict) -> Dict:
    """Optimize tool arguments for better execution"""
    
    optimized_args = args.copy()
    
    # Common optimizations
    if tool_name == 'type_text':
        # Ensure text is string
        if 'text' in optimized_args and not isinstance(optimized_args['text'], str):
            optimized_args['text'] = str(optimized_args['text'])
    
    elif tool_name == 'click_element':
        # Add timeout if not specified
        if 'timeout' not in optimized_args:
            optimized_args['timeout'] = 10000  # 10 seconds
    
    elif tool_name == 'navigate_to':
        # Ensure URL is properly formatted
        if 'url' in optimized_args:
            url = optimized_args['url']
            if not url.startswith(('http://', 'https://')):
                optimized_args['url'] = f"https://{url}"
    
    return optimized_args