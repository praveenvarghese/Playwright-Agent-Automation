import os
import json
import re
from datetime import datetime, timezone
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import uuid  # For generating unique IDs for acceptance criteria

# Load environment variables
load_dotenv()

class FeatureProcessor:
    def __init__(self):
        """
        Initialize the feature processor with Azure Cognitive Search configurations.
        """
        # Azure Cognitive Search Configuration
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        self.feature_index_name = os.getenv("AZURE_SEARCH_FEATURE_INDEX", "features-index")
        
        # Validate configurations
        self._validate_config()
        
        # Initialize Search client
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.feature_index_name,
            credential=AzureKeyCredential(self.search_key)
        )
        
        # Define paths
        self.PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.REGISTRY_PATH = os.path.join(self.PROJECT_ROOT, "data", "feature_registry.json")
        self.REQUIREMENTS_DIR = os.path.join(self.PROJECT_ROOT, "prompts")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.REGISTRY_PATH), exist_ok=True)
        os.makedirs(self.REQUIREMENTS_DIR, exist_ok=True)
        
        # Initialize or load feature registry
        self.registry = self._load_registry()
    
    def _validate_config(self):
        """Validate that all required configuration values are present."""
        missing_vars = []
        
        # Check Azure Search config
        if not self.search_endpoint:
            missing_vars.append("AZURE_SEARCH_ENDPOINT")
        if not self.search_key:
            missing_vars.append("AZURE_SEARCH_KEY")
            
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    def _load_registry(self):
        """Load the feature registry from the JSON file, or create it if it doesn't exist."""
        try:
            if os.path.exists(self.REGISTRY_PATH):
                with open(self.REGISTRY_PATH, 'r') as f:
                    return json.load(f)
            else:
                # Initialize empty registry
                registry = {
                    "features": {},
                    "domain_counters": {}
                }
                # Save the empty registry
                with open(self.REGISTRY_PATH, 'w') as f:
                    json.dump(registry, f, indent=2)
                return registry
        except Exception as e:
            print(f"Error loading registry: {str(e)}")
            # Return a default empty registry
            return {"features": {}, "domain_counters": {}}
    
    def _save_registry(self):
        """Save the feature registry to the JSON file."""
        try:
            with open(self.REGISTRY_PATH, 'w') as f:
                json.dump(self.registry, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving registry: {str(e)}")
            return False
    
    def _generate_feature_id(self, title, description):
        """Generate a unique feature ID based on title and description."""
        # Extract domain code from title or description
        domain_code = self._extract_domain_code(title, description)
        
        # Get or initialize the counter for this domain
        if domain_code not in self.registry["domain_counters"]:
            self.registry["domain_counters"][domain_code] = 0
        
        # Increment the counter
        self.registry["domain_counters"][domain_code] += 1
        counter = self.registry["domain_counters"][domain_code]
        
        # Format the feature ID
        feature_id = f"FEAT-{domain_code}-{counter:03d}"
        
        # Save the updated registry
        self._save_registry()
        
        return feature_id
        
    def update_feature_test_cases(self, feature_id, test_case_ids):
        """
        Update the list of test case IDs associated with a feature.
        
        Args:
            feature_id (str): The feature ID
            test_case_ids (list): List of test case IDs to associate with the feature
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the current feature document
            results = list(self.search_client.search(
                search_text="",
                filter=f"id eq '{feature_id}'",
                select=["*"]  # Select all fields to ensure we get the complete document
            ))
            
            if not results:
                print(f"Feature with ID {feature_id} not found.")
                return False
            
            feature_doc = results[0]
            
            # Get current test case IDs or initialize as empty list
            current_test_case_ids = feature_doc.get("testCaseIds", []) or []
            
            # Convert to sets for more efficient comparison and merging
            current_set = set(current_test_case_ids)
            new_set = set(test_case_ids)
            
            # Find only the new test case IDs
            test_cases_to_add = new_set - current_set
            
            # If no changes, return early
            if not test_cases_to_add:
                print(f"No new test cases to add for feature {feature_id}")
                return True
            
            # Update the document with combined test case IDs
            updated_test_case_ids = list(current_set | new_set)
            
            # Create a complete document copy with only the fields to update
            update_doc = dict(feature_doc)  # Create a complete copy of the document
            update_doc["testCaseIds"] = updated_test_case_ids  # Update just the test case IDs
            update_doc["lastUpdated"] = datetime.now(timezone.utc).isoformat()  # Update the timestamp
            
            # Upload the complete document with updates
            self.search_client.upload_documents(documents=[update_doc])
            
            print(f"Successfully updated feature {feature_id} with {len(test_cases_to_add)} new test cases (total: {len(updated_test_case_ids)})")
            return True
            
        except Exception as e:
            print(f"Error updating feature test cases: {str(e)}")
            return False
    
    def _extract_domain_code(self, title, description):
        """Extract a domain code from the title or description."""
        # Dictionary of domain keywords to codes
        domain_keywords = {
            "environment": "ENV",
            "user": "USR",
            "dashboard": "DASH",
            "team": "TEAM",
            "authentication": "AUTH",
            "notification": "NOTIF",
            "report": "RPT",
            "integration": "INTG"
        }
        
        # Combine title and description for analysis
        combined_text = f"{title} {description}".lower()
        
        # Check for domain keywords
        for keyword, code in domain_keywords.items():
            if keyword in combined_text:
                return code
        
        # Default to GEN (Generic) if no domain is detected
        return "GEN"
    
    def read_feature_requirement(self, file_path):
        """
        Read and parse a feature requirement file.
        
        Args:
            file_path (str): Path to the feature requirement file
            
        Returns:
            dict: Parsed feature requirement
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Initialize feature dict
            feature = {}
            
            # Parse the TYPE
            type_match = re.search(r'TYPE:\s*(\w+)', content)
            if type_match:
                feature['type'] = type_match.group(1).strip()
            
            # Parse the TITLE
            title_match = re.search(r'TITLE:\s*(.+?)(?=\n\w+:|$)', content, re.DOTALL)
            if title_match:
                feature['title'] = title_match.group(1).strip()
            
            # Parse the DESCRIPTION
            desc_match = re.search(r'DESCRIPTION:\s*(.+?)(?=\n\w+:|$)', content, re.DOTALL)
            if desc_match:
                feature['description'] = desc_match.group(1).strip()
            
            # Parse the ACCEPTANCE_CRITERIA
            criteria_match = re.search(r'ACCEPTANCE_CRITERIA:\s*(.+?)(?=\n\w+:|$)', content, re.DOTALL)
            if criteria_match:
                criteria_text = criteria_match.group(1).strip()
                # Split by bullet points
                criteria_list = [item.strip() for item in criteria_text.split('\n-') if item.strip()]
                # Clean up the first item which may not start with a dash
                if criteria_list and not criteria_list[0].startswith('-'):
                    criteria_list[0] = criteria_list[0].lstrip('- ')
                feature['acceptance_criteria'] = criteria_list
            
            # Parse the RELATED_FEATURES
            related_match = re.search(r'RELATED_FEATURES:\s*(.+?)(?=\n\w+:|$)', content, re.DOTALL)
            if related_match:
                related_text = related_match.group(1).strip()
                if related_text:
                    feature['related_features'] = [id.strip() for id in related_text.split(',')]
                else:
                    feature['related_features'] = []
            else:
                feature['related_features'] = []
            
            return feature
        
        except Exception as e:
            print(f"Error reading feature requirement: {str(e)}")
            return None
    
    def process_feature(self, feature_data):
        """
        Process a feature based on its type (NEW/UPDATE/REMOVE).
        
        Args:
            feature_data (dict): The parsed feature data
            
        Returns:
            dict: Processed feature with assigned ID
        """
        feature_type = feature_data.get('type', '').upper()
        feature_title = feature_data.get('title', '')
        
        if not feature_type or not feature_title:
            raise ValueError("Feature is missing required type or title")
        
        # Check if this feature already exists in the registry
        existing_feature_id = None
        for title, info in self.registry['features'].items():
            # Case-insensitive comparison
            if title.lower() == feature_title.lower():
                existing_feature_id = info['id']
                break
        
        if feature_type == 'NEW':
            if existing_feature_id:
                print(f"Warning: Feature with title '{feature_title}' already exists with ID {existing_feature_id}")
                feature_data['id'] = existing_feature_id
            else:
                # Generate a new feature ID
                feature_id = self._generate_feature_id(
                    feature_data.get('title', ''),
                    feature_data.get('description', '')
                )
                feature_data['id'] = feature_id
                
                # Add to registry
                self.registry['features'][feature_title] = {
                    'id': feature_id,
                    'latest_version': 1,
                    'status': 'active',
                    'created': datetime.now(timezone.utc).isoformat(),
                    'updated': datetime.now(timezone.utc).isoformat()
                }
                self._save_registry()
        
        elif feature_type == 'UPDATE':
            if existing_feature_id:
                feature_data['id'] = existing_feature_id
                
                # Update registry
                self.registry['features'][feature_title]['latest_version'] += 1
                self.registry['features'][feature_title]['updated'] = datetime.now(timezone.utc).isoformat()
                self._save_registry()
            else:
                print(f"Warning: Cannot update non-existent feature '{feature_title}'. Creating as NEW instead.")
                # Treat as NEW
                feature_id = self._generate_feature_id(
                    feature_data.get('title', ''),
                    feature_data.get('description', '')
                )
                feature_data['id'] = feature_id
                
                # Add to registry
                self.registry['features'][feature_title] = {
                    'id': feature_id,
                    'latest_version': 1,
                    'status': 'active',
                    'created': datetime.now(timezone.utc).isoformat(),
                    'updated': datetime.now(timezone.utc).isoformat()
                }
                self._save_registry()
        
        elif feature_type == 'REMOVE':
            if existing_feature_id:
                feature_data['id'] = existing_feature_id
                
                # Update registry
                self.registry['features'][feature_title]['status'] = 'deprecated'
                self.registry['features'][feature_title]['updated'] = datetime.now(timezone.utc).isoformat()
                self._save_registry()
            else:
                raise ValueError(f"Cannot remove non-existent feature '{feature_title}'")
        
        return feature_data
    
    def store_feature(self, feature_data):
        """
        Store a feature in the Azure Cognitive Search index.
        
        Args:
            feature_data (dict): The processed feature data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Prepare acceptance criteria as complex types
            acceptance_criteria = []
            for i, criteria in enumerate(feature_data.get('acceptance_criteria', [])):
                acceptance_criteria.append({
                    "id": f"AC-{i+1:03d}",
                    "description": criteria,
                    "status": "Active",
                    "addedDate": datetime.now(timezone.utc).isoformat()
                })
            
            # Prepare document for Cognitive Search
            search_doc = {
                "id": feature_data['id'],
                "name": feature_data['title'],  # Using 'name' instead of 'title'
                "description": feature_data['description'],
                "status": self.registry['features'][feature_data['title']]['status'],
                "version": str(self.registry['features'][feature_data['title']]['latest_version']),
                "createdDate": self.registry['features'][feature_data['title']]['created'],
                "lastUpdated": self.registry['features'][feature_data['title']]['updated'],  # 'lastUpdated' instead of 'updatedDate'
                "acceptanceCriteria": acceptance_criteria,
                "testCaseIds": []  # Initialize with empty array of test case IDs
            }
            
            # Upload to Azure Cognitive Search
            self.search_client.upload_documents(documents=[search_doc])
            print(f"Successfully uploaded feature: {feature_data['id']}")
            
            return True
        
        except Exception as e:
            print(f"Error storing feature: {str(e)}")
            return False
    
    def process_and_store_feature_file(self, file_path):
        """
        Process a feature requirement file and store the feature in the database.
        
        Args:
            file_path (str): Path to the feature requirement file
            
        Returns:
            dict: The processed and stored feature data
        """
        # Read the feature requirement
        feature_data = self.read_feature_requirement(file_path)
        if not feature_data:
            print(f"Failed to read feature requirement from {file_path}")
            return None
        
        # Process the feature based on its type
        try:
            processed_feature = self.process_feature(feature_data)
            
            # Store the feature in the database
            success = self.store_feature(processed_feature)
            
            if success:
                print(f"Successfully processed and stored feature: {processed_feature['id']}")
                return processed_feature
            else:
                print(f"Failed to store feature from {file_path}")
                return None
        
        except Exception as e:
            print(f"Error processing feature: {str(e)}")
            return None

    # Add these methods to your FeatureProcessor class in feature_processor.py

    def update_feature_with_criteria(self, feature_id, feature_data, updated_criteria, preserve_test_cases=True):
        """
        Update a feature with new criteria while preserving test case links and deprecated criteria.
        """
        try:
            # Get existing test case IDs if preserving
            existing_test_case_ids = []
            if preserve_test_cases:
                existing_test_case_ids = self.get_existing_test_case_ids(feature_id)
            
            # Debug logging
            deprecated_count = sum(1 for c in updated_criteria if c.get('status') == 'Deprecated')
            print(f"🔹 Updating feature {feature_id} with {len(updated_criteria)} criteria objects, including {deprecated_count} deprecated")
                
            # Prepare document for Cognitive Search - include ALL criteria
            search_doc = {
                "id": feature_id,
                "name": feature_data.get('title', ''),
                "description": feature_data.get('description', ''),
                "status": self.registry['features'][feature_data['title']]['status'],
                "version": str(self.registry['features'][feature_data['title']]['latest_version']),
                "createdDate": self.registry['features'][feature_data['title']]['created'],
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
                "acceptanceCriteria": updated_criteria,  # Include ALL criteria, including deprecated
                "testCaseIds": existing_test_case_ids
            }
            
            # Extra verification to ensure deprecated criteria are included
            for i, criteria in enumerate(updated_criteria):
                if criteria.get('status') == 'Deprecated':
                    print(f"🔹 Including deprecated criteria in position {i}: {criteria.get('id')}")
            
            # Upload to Azure Cognitive Search
            try:
                self.search_client.upload_documents(documents=[search_doc])
                print(f"✅ Successfully updated feature: {feature_id} with {len(updated_criteria)} criteria")
                
                # Verify update was successful
                # This would fetch the document again to confirm deprecated criteria were stored
                return True
            except Exception as e:
                print(f"⚠️ Error during database update: {str(e)}")
                return False
                
        except Exception as e:
            print(f"⚠️ Error updating feature: {str(e)}")
            return False
    
    def get_existing_test_case_ids(self, feature_id):
        """
        Get existing test case IDs for a feature.
        
        Args:
            feature_id (str): The feature ID
            
        Returns:
            list: List of test case IDs
        """
        try:
            results = list(self.search_client.search(
                search_text="",
                filter=f"id eq '{feature_id}'",
                select=["testCaseIds"]
            ))
            
            if results and results[0].get("testCaseIds"):
                return results[0].get("testCaseIds")
            return []
        
        except Exception as e:
            print(f"Error getting test case IDs: {str(e)}")
            return []

    def merge_acceptance_criteria(self, original_criteria, updated_criteria):
        """
        Merge original and updated acceptance criteria intelligently.
        Preserves IDs where possible and tracks history of changes.
        
        Args:
            original_criteria (list): List of original criteria objects
            updated_criteria (list): List of updated criteria objects
            
        Returns:
            list: Merged list of criteria objects
        """
        # Create maps for quick lookup
        original_by_id = {c.get("id"): c for c in original_criteria if c.get("id")}
        updated_by_id = {c.get("id"): c for c in updated_criteria if c.get("id")}
        
        # Start with all updated criteria
        result = list(updated_criteria)
        
        for original_id, original in original_by_id.items():
            if original_id not in updated_by_id:
                # This criteria was removed, mark it as deprecated
                deprecated = dict(original)
                deprecated["status"] = "Deprecated"
                # Use addedDate instead of removedDate to avoid schema issues
                deprecated["addedDate"] = datetime.now(timezone.utc).isoformat()
                result.append(deprecated)
        
        return result

# Example usage
if __name__ == "__main__":
    processor = FeatureProcessor()
    
    # Example file path
    feature_file = os.path.join(processor.REQUIREMENTS_DIR, "feature_requirement.txt")
    
    if os.path.exists(feature_file):
        result = processor.process_and_store_feature_file(feature_file)
        if result:
            print(f"Feature processed successfully with ID: {result['id']}")
    else:
        print(f"Feature file not found: {feature_file}")