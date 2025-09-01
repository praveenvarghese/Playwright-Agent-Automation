"""
Test case fetching and validation from multiple sources
"""

import os
from dotenv import load_dotenv
from models.schemas import TestCase
from pydantic import ValidationError
from common.vector_retrieval import fetch_test_case_by_id
from common.azure_devops_client import fetch_from_azure_devops

load_dotenv()

async def fetch_test_case(test_case_id):
    """Fetch test case from configured source WITH VALIDATION"""
    source = os.getenv("TEST_CASE_SOURCE", "vector").lower()
    
    raw_test_case = None
    
    if source == "azure_devops":
        print(f"📄 Loading test case from Azure DevOps: {test_case_id}")
        try:
            raw_test_case = await fetch_from_azure_devops(test_case_id)
        except Exception as e:
            print(f"❌ Error loading from Azure DevOps: {e}")
            return None
    
    elif source == "file":
        print(f"📄 Loading test case from file: {test_case_id}")
        try:
            raw_test_case = await fetch_from_file(test_case_id)
        except Exception as e:
            print(f"❌ Error loading file: {e}")
            return None
    
    else:  # vector (default)
        print(f"🔍 Searching for test case ID: {test_case_id}")
        try:
            raw_test_case = await fetch_test_case_by_id(test_case_id)
            if raw_test_case:
                print(f"✅ Found: {raw_test_case.get('title', 'Unknown')}")
            else:
                print("⚠️ Test case not found.")
                return None
        except Exception as e:
            print(f"❌ Azure Search error: {str(e)}")
            return None
    
    # Validate with Pydantic
    if raw_test_case:
        try:
            validated_test_case = TestCase(**raw_test_case)
            print(f"✅ Test case validated successfully")
            return validated_test_case.model_dump()  # Return as dict for compatibility
        except ValidationError as e:
            print(f"❌ Test case validation failed: {e}")
            print("Raw data keys:", list(raw_test_case.keys()) if isinstance(raw_test_case, dict) else "Not a dict")
            return None
    
    return None

async def fetch_from_file(test_case_id):
    """Fetch test case from local file"""
    with open(test_case_id, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    raw_test_case = {
        'id': 'TC-FILE-001',
        'title': '',
        'steps': '',
        'expectedResults': ''
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'id':
                raw_test_case['id'] = value
            elif key == 'title':
                raw_test_case['title'] = value
                current_section = None
            elif key == 'steps':
                current_section = 'steps'
                raw_test_case['steps'] = value if value else ''
            elif key == 'expected':
                current_section = 'expectedResults'
                raw_test_case['expectedResults'] = value if value else ''
        elif current_section and line:
            if raw_test_case[current_section]:
                raw_test_case[current_section] += '\n' + line
            else:
                raw_test_case[current_section] = line
    
    print(f"✅ Loaded from file: {raw_test_case.get('title', 'Unknown')}")
    return raw_test_case