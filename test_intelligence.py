#!/usr/bin/env python3
"""
Test script for the Project Intelligence Scanner
"""

import sys
import json
from pathlib import Path

# Add project to path - we're inside playwright_generation
project_root = Path(__file__).parent.parent  # Go up one level to get to root
sys.path.insert(0, str(project_root))

from intelligence.project_intelligence import create_project_intelligence

def test_intelligence_scanner():
    """Test the intelligence scanner with your actual project"""
    
    # Your project path
    project_path = r"C:\Users\VARGHESE\code\portal\e2e"
    
    print(f"🧪 Testing Intelligence Scanner")
    print(f"📁 Project path: {project_path}")
    
    # Debug: Check if path exists and what's in it
    project_pathlib = Path(project_path)
    if not project_pathlib.exists():
        print(f"❌ Project path does not exist!")
        return False
    
    print(f"🔍 Contents of {project_path}:")
    for item in project_pathlib.iterdir():
        if item.is_dir():
            file_count = len(list(item.glob('**/*')))
            print(f"  📁 {item.name}/ ({file_count} total items)")
        else:
            print(f"  📄 {item.name}")
    
    try:
        # Create intelligence instance
        intelligence = create_project_intelligence(project_path)
        
        # Analyze project
        analysis = intelligence.analyze_project_structure()
        
        # Print results
        print("\n" + "="*50)
        print("📊 PROJECT ANALYSIS RESULTS")
        print("="*50)
        
        print(f"\n📁 DIRECTORIES:")
        for dir_name, info in analysis['directories'].items():
            status = "✅" if info['exists'] else "❌"
            count = info.get('count', 0)
            print(f"  {status} {dir_name}: {count} JS/TS files")
            
            # Show all files found for debugging
            all_files = info.get('all_files', [])
            if all_files:
                print(f"    All files found: {all_files[:5]}...")  # Show first 5
            else:
                print(f"    No files found in directory")
            print(f"  {status} {dir_name}: {count} files")
        
        print(f"\n📄 PAGE OBJECTS:")
        if analysis['pages']['exists']:
            print(f"  Classes found: {len(analysis['pages']['classes'])}")
            for class_name in analysis['pages']['classes']:
                methods = analysis['pages']['methods'].get(class_name, [])
                print(f"    {class_name}: {len(methods)} methods")
        else:
            print("  No page objects found")
        
        print(f"\n🧪 TEST FILES:")
        if analysis['tests']['exists']:
            print(f"  Test files: {len(analysis['tests']['files'])}")
            for test_file in analysis['tests']['files']:
                print(f"    {test_file['name']}: {len(test_file['test_cases'])} tests")
        else:
            print("  No test files found")
        
        # Test decision making
        print(f"\n🤔 DECISION TESTING:")
        sample_request = {
            'title': 'Edit user profile information',
            'steps': [
                'Login to application',
                'Navigate to user profile',
                'Edit user information',
                'Save changes'
            ]
        }
        
        decisions = intelligence.make_integration_decisions(sample_request)
        print(f"  Sample test request: {sample_request['title']}")
        print(f"  Spec decision: {decisions['spec_decision']}")
        print(f"  Page decision: {decisions['page_decision']}")
        print(f"  Reusable methods: {decisions['method_reuse']}")
        
        print(f"\n✅ Intelligence scanner test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_intelligence_scanner()
    sys.exit(0 if success else 1)