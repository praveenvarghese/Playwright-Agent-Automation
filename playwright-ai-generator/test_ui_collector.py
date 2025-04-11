import asyncio
import json
import os
import sys

# Add the correct path to import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'playwright-ai-generator')))
from core.ui_element_collector import UIElementCollector

async def main():
    """Test the UI element collector to verify it can authenticate and collect elements."""
    print("\n=== TESTING UI ELEMENT COLLECTOR ===")
    
    # Create the collector
    collector = UIElementCollector()
    
    try:
        # Specify a path to collect elements from (default is "/")
        path = "/"
        if len(sys.argv) > 1:
            path = sys.argv[1]
            
        print(f"Collecting elements from path: {path}")
        
        # Collect elements (this handles authentication)
        elements = await collector.collect_elements(path)
        
        # Report results
        print(f"\nSuccessfully collected {len(elements)} UI elements")
        
        # Save elements to a JSON file for review
        output_file = "collected_elements.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(elements, f, indent=2)
            
        print(f"Elements saved to {output_file}")
        
        # Show a few example elements
        if elements:
            print("\nExample elements:")
            for i, elem in enumerate(elements[:5]):
                print(f"{i+1}. {elem['type']} - Text: '{elem['text'][:30]}...' - Selector: {elem['selector']}")
        
    except Exception as e:
        print(f"Error testing UI element collector: {str(e)}")
    finally:
        # Always close the browser
        await collector.close()

if __name__ == "__main__":
    asyncio.run(main())