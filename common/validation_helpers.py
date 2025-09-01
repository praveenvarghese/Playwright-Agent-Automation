"""
Validation helpers for agent responses and environment setup
"""

import os
import sys
import json
import re
from models.schemas import POMGeneratorResponse, TestGeneratorResponse

def validate_agent_response(response_content: str, expected_type: str):
    """Validate agent responses against expected format"""
    try:
        if expected_type == "pom":
            # Try to parse as POM Generator response
            if "```json" in response_content:
                json_match = re.search(r'```json\s*(.*?)```', response_content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(1))
                    validated = POMGeneratorResponse(**parsed)
                    print("✅ POM response format validated")
                    return True
            # Fallback validation - check for basic structure
            elif "export class" in response_content and "pages/" in response_content:
                print("✅ POM response has basic structure")
                return True
                
        elif expected_type == "test":
            # Basic test validation
            if "test(" in response_content and "import" in response_content:
                print("✅ Test response format validated")
                return True
                
    except Exception as e:
        print(f"⚠️ Agent response validation failed: {e}")
        return False
    
    return False

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

def check_pydantic_models():
    """Check if Pydantic models are available"""
    try:
        import models.schemas
        print("✅ Pydantic models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Missing Pydantic models: {e}")
        print("Make sure to install: pip install pydantic")
        print("And create the models/ directory with schemas.py")
        return False