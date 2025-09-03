"""
Validation helpers for agent responses and environment setup
"""

import os
import sys
import json
import re
from models.schemas import POMGeneratorResponse, TestGeneratorResponse

def validate_agent_response(response_content: str, expected_type: str):
    """Validate agent responses against expected format (UPDATED: supports both POM and Test JSON)"""
    try:
        if expected_type == "pom":
            # Validate POM JSON format
            if "```json" in response_content:
                json_match = re.search(r'```json\s*(.*?)```', response_content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(1))
                    if 'files' in parsed and parsed['files']:
                        print("✅ POM response format validated")
                        return True
            # Fallback validation
            elif "export class" in response_content and "pages/" in response_content:
                print("✅ POM response has basic structure")
                return True
                
        elif expected_type == "test":
            # NEW: Validate Test JSON format
            if "```json" in response_content:
                json_match = re.search(r'```json\s*(.*?)```', response_content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(1))
                    if 'test_file' in parsed and parsed['test_file'].get('content'):
                        print("✅ Test response JSON format validated")
                        return True
            # Fallback validation for old format
            elif "test(" in response_content and "import" in response_content:
                print("✅ Test response has basic structure (legacy format)")
                return True
                
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parsing failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Agent response validation failed: {e}")
        return False
    
    print(f"⚠️ {expected_type} response format validation failed")
    return False

def validate_test_method_calls(test_content: str, available_methods: dict):
    """Validate that test method calls exist in POMs (NEW)"""
    issues = []
    
    # Extract test method calls
    from orchestration.extraction_utils import extract_test_method_calls, validate_method_consistency
    
    test_calls = extract_test_method_calls(test_content)
    issues = validate_method_consistency(available_methods, test_calls)
    
    if issues:
        print("❌ Test method validation failed:")
        for issue in issues:
            print(f"  {issue}")
        return False
    
    print("✅ Test method calls validated against POMs")
    return True

def setup_environment():
    """Validate required environment variables"""
    required_vars = [
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", 
        "AZURE_OPENAI_DEPLOYMENT_NAME", "APP_URL", "APP_USERNAME", "APP_PASSWORD"
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import models.schemas
        print("✅ Schema models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Missing schema models: {e}")
        print("Make sure to install: pip install pydantic")
        print("And create the models/ directory with schemas.py")
        return False