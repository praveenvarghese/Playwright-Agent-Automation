import os
import aiohttp
import base64
import json
import xml.etree.ElementTree as ET
import re
from dotenv import load_dotenv

async def fetch_from_azure_devops(work_item_id):
    """
    Fetch test case from Azure DevOps Test Plans
    
    Args:
        work_item_id (str): Work item ID (e.g., "12345")
        
    Returns:
        dict or None: Standardized test case format
    """
    print(f"🔍 Fetching test case from Azure DevOps: {work_item_id}")
    
    # Load configuration
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(dotenv_path)
    
    org_url = os.getenv("AZURE_DEVOPS_ORG_URL")
    project = os.getenv("AZURE_DEVOPS_PROJECT") 
    pat = os.getenv("AZURE_DEVOPS_PAT")
    
    if not (org_url and project and pat):
        raise ValueError("Azure DevOps config missing. Check .env file for AZURE_DEVOPS_ORG_URL, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_PAT")
    
    # Clean work item ID (remove any prefixes)
    clean_id = str(work_item_id).replace("WI-", "").replace("TC-", "").replace("ADO-", "")
    
    # Validate it's numeric
    if not clean_id.isdigit():
        print(f"❌ Invalid work item ID format: {work_item_id}")
        return None
    
    # Prepare authentication
    auth = base64.b64encode(f":{pat}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Azure DevOps Work Items API URL
    api_url = f"{org_url}/{project}/_apis/wit/workitems/{clean_id}?$expand=all&api-version=7.0"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    work_item = await response.json()
                    return _map_azure_workitem_to_testcase(work_item)
                elif response.status == 404:
                    print(f"⚠️ Work item {work_item_id} not found in Azure DevOps")
                    return None
                elif response.status == 401:
                    print(f"❌ Authentication failed. Check your AZURE_DEVOPS_PAT")
                    return None
                elif response.status == 403:
                    print(f"❌ Access denied. Check your PAT permissions (need Work Items: Read)")
                    return None
                else:
                    error_text = await response.text()
                    print(f"❌ Azure DevOps API error: {response.status} - {error_text}")
                    return None
                    
    except Exception as e:
        print(f"❌ Error fetching from Azure DevOps: {str(e)}")
        return None

def _map_azure_workitem_to_testcase(work_item):
    """Map Azure DevOps work item to standard test case format"""
    fields = work_item.get('fields', {})
    
    # Extract basic info
    work_item_id = work_item.get('id')
    title = fields.get('System.Title', 'Untitled Test Case')
    work_item_type = fields.get('System.WorkItemType', '')
    
    # Validate it's a test case
    if work_item_type.lower() != 'test case':
        print(f"⚠️ Warning: Work item {work_item_id} is type '{work_item_type}', not 'Test Case'")
    
    # Extract test steps (Azure DevOps stores steps in XML format)
    steps_xml = fields.get('Microsoft.VSTS.TCM.Steps', '')
    steps_text = _parse_azure_steps(steps_xml)
    
    # Extract acceptance criteria or description as expected results
    expected_results = (
        fields.get('Microsoft.VSTS.Common.AcceptanceCriteria', '') or
        fields.get('System.Description', '') or
        'Test should complete successfully'
    )
    
    # Return in standard format (same as vector_retrieval.py)
    test_case = {
        'id': f"ADO-{work_item_id}",
        'title': title,
        'steps': steps_text,
        'expectedResults': _clean_html(expected_results),
        'source': 'azure_devops',
        'metadata': {
            'work_item_id': work_item_id,
            'work_item_type': work_item_type,
            'work_item_url': work_item.get('_links', {}).get('html', {}).get('href', ''),
            'state': fields.get('System.State', ''),
            'assigned_to': fields.get('System.AssignedTo', {}).get('displayName', '') if fields.get('System.AssignedTo') else '',
            'area_path': fields.get('System.AreaPath', ''),
            'iteration_path': fields.get('System.IterationPath', '')
        }
    }
    
    print(f"✅ Loaded from Azure DevOps: {title} (Type: {work_item_type})")
    return test_case

def _parse_azure_steps(steps_xml):
    """Parse Azure DevOps test steps XML into readable text"""
    if not steps_xml:
        return "No steps defined"
    
    try:
        # Azure DevOps stores test steps in XML format
        steps_text = ""
        step_counter = 1
        
        # Try to parse as XML
        if steps_xml.strip().startswith('<'):
            try:
                root = ET.fromstring(f"<root>{steps_xml}</root>")
                steps = root.findall('.//step')
                
                for step in steps:
                    # Extract action (parameterizedString)
                    action_elem = step.find('.//parameterizedString')
                    if action_elem is not None:
                        action_text = _clean_html(action_elem.text or "")
                        if action_text.strip():
                            steps_text += f"{step_counter}. {action_text.strip()}\n"
                            step_counter += 1
                
                if steps_text.strip():
                    return steps_text.strip()
                    
            except ET.ParseError:
                # Fallback to regex parsing if XML parsing fails
                pass
        
        # Fallback: Use regex to extract steps
        if '<step' in steps_xml.lower():
            # Extract parameterizedString content
            action_pattern = r'<parameterizedString[^>]*>(.*?)</parameterizedString>'
            actions = re.findall(action_pattern, steps_xml, re.DOTALL | re.IGNORECASE)
            
            for i, action in enumerate(actions, 1):
                clean_action = _clean_html(action)
                if clean_action.strip():
                    steps_text += f"{i}. {clean_action.strip()}\n"
        else:
            # Plain text fallback
            steps_text = _clean_html(steps_xml)
        
        return steps_text.strip() if steps_text.strip() else "Steps not properly formatted"
        
    except Exception as e:
        print(f"⚠️ Warning: Could not parse steps XML: {e}")
        return _clean_html(steps_xml) or "Steps parsing failed"

def _clean_html(text):
    """Remove HTML tags and clean up text"""
    if not text:
        return ""
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', str(text))
    
    # Replace HTML entities
    clean = clean.replace('&nbsp;', ' ')
    clean = clean.replace('&lt;', '<')
    clean = clean.replace('&gt;', '>')
    clean = clean.replace('&amp;', '&')
    clean = clean.replace('&#39;', "'")
    clean = clean.replace('&quot;', '"')
    
    # Clean up whitespace
    clean = re.sub(r'\s+', ' ', clean)
    clean = clean.strip()
    
    return clean

async def test_azure_devops_connection():
    """Test function to verify Azure DevOps connection and PAT"""
    print("🧪 Testing Azure DevOps connection...")
    
    # Load config
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(dotenv_path)
    
    org_url = os.getenv("AZURE_DEVOPS_ORG_URL")
    project = os.getenv("AZURE_DEVOPS_PROJECT") 
    pat = os.getenv("AZURE_DEVOPS_PAT")
    
    if not (org_url and project and pat):
        print("❌ Missing Azure DevOps configuration")
        return False
    
    # Test with a simple API call to list work item types
    auth = base64.b64encode(f":{pat}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    test_url = f"{org_url}/{project}/_apis/wit/workitemtypes?api-version=7.0"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    work_item_types = [wit['name'] for wit in data.get('value', [])]
                    print(f"✅ Connection successful!")
                    print(f"📋 Available work item types: {', '.join(work_item_types)}")
                    
                    # Check if Test Case type exists
                    if 'Test Case' in work_item_types:
                        print("✅ 'Test Case' work item type found")
                    else:
                        print("⚠️ 'Test Case' work item type not found")
                    
                    return True
                else:
                    print(f"❌ Connection failed: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    """Test the Azure DevOps client when running directly"""
    import asyncio
    
    async def main():
        # Test connection
        await test_azure_devops_connection()
        
        # Test fetching a work item (you'll need to provide a real ID)
        test_id = input("Enter a work item ID to test (or press Enter to skip): ").strip()
        if test_id:
            result = await fetch_from_azure_devops(test_id)
            if result:
                print("\n✅ Test case fetched successfully:")
                print(f"ID: {result['id']}")
                print(f"Title: {result['title']}")
                print(f"Steps: {result['steps'][:100]}...")
                print(f"Expected: {result['expectedResults'][:100]}...")
            else:
                print("❌ Failed to fetch test case")
    
    asyncio.run(main())