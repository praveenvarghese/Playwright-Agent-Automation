"""
Project intelligence scanner for Playwright test generation.
Uses tree-sitter AST parsing for reliable code analysis.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import tree_sitter_typescript as ts_typescript
    from tree_sitter import Language, Parser, Node
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    print("⚠️ tree-sitter not available, falling back to text parsing")

class ProjectIntelligence:
    """Analyzes existing Playwright project using AST parsing for reliability"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.parser = None
        self._init_parser()
        
    def _init_parser(self):
        """Initialize tree-sitter parser for TypeScript"""
        if HAS_TREE_SITTER:
            try:
                # Create TypeScript language
                TS_LANGUAGE = Language(ts_typescript.language_typescript())
                
                # Create parser
                self.parser = Parser()
                self.parser.set_language(TS_LANGUAGE)
                print("✅ Tree-sitter TypeScript parser initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize tree-sitter: {e}")
                self.parser = None
        
    def analyze_project_structure(self) -> Dict[str, Any]:
        """Analyze project structure using AST parsing"""
        print(f"🔍 Analyzing project structure: {self.project_path}")
        
        analysis = {
            'directories': self._scan_directories(),
            'pages': self._analyze_page_objects_ast(),
            'tests': self._analyze_test_files_ast(),
            'patterns': self._extract_patterns(),
            'reusable_methods': self._find_reusable_methods()
        }
        
        print(f"✅ Project analysis complete")
        return analysis
    
    def _scan_directories(self) -> Dict[str, Any]:
        """Scan and categorize directories - discover directories dynamically"""
        directories = {}
        
        # Discover directories that contain JS/TS files
        if self.project_path.exists():
            for item in self.project_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    js_files = self._get_js_files(item)
                    if js_files:  # Only include directories with JS/TS files
                        directories[item.name] = {
                            'exists': True,
                            'files': js_files,
                            'count': len(js_files),
                            'all_files': [str(f.relative_to(self.project_path)) for f in item.glob('**/*') if f.is_file()]
                        }
        
        return directories
    
    def _get_js_files(self, directory: Path) -> List[str]:
        """Get all JavaScript/TypeScript files in directory"""
        js_files = []
        if directory.exists():
            for pattern in ['**/*.js', '**/*.ts', '**/*.jsx', '**/*.tsx']:
                for file_path in directory.glob(pattern):
                    js_files.append(str(file_path.relative_to(self.project_path)))
        return js_files
    
    def _analyze_page_objects_ast(self) -> Dict[str, Any]:
        """Analyze page objects using tree-sitter AST parsing"""
        # Dynamically find directories that might contain page objects
        directories = self._scan_directories()
        page_dirs = []
        
        # Look for directories that likely contain page objects
        for dir_name, dir_info in directories.items():
            if dir_info.get('exists') and dir_info.get('count', 0) > 0:
                # Check if directory has files with 'Page' in the name or common page patterns
                files = dir_info.get('files', [])
                if any('page' in f.lower() or 'Page' in f for f in files):
                    page_dirs.append(dir_name)
        
        # If no obvious page directories, use all directories with TS/JS files
        if not page_dirs:
            page_dirs = [name for name, info in directories.items() if info.get('exists')]
        
        page_analysis = {
            'exists': len(page_dirs) > 0,
            'classes': [],
            'methods': {},
            'imports': [],
            'patterns': {},
            'directories_scanned': page_dirs
        }
        
        for dir_name in page_dirs:
            dir_path = self.project_path / dir_name
            if dir_path.exists():
                for page_file in dir_path.glob('**/*'):
                    if page_file.suffix in ['.js', '.ts', '.jsx', '.tsx'] and page_file.is_file():
                        try:
                            ast_data = self._parse_typescript_file(page_file)
                            if ast_data:
                                # Extract classes
                                for class_info in ast_data.get('classes', []):
                                    class_name = class_info['name']
                                    page_analysis['classes'].append(class_name)
                                    page_analysis['methods'][class_name] = class_info.get('methods', [])
                                
                                # Extract imports
                                page_analysis['imports'].extend(ast_data.get('imports', []))
                                
                        except Exception as e:
                            print(f"⚠️ Could not analyze {page_file}: {e}")
        
        return page_analysis
    
    def _analyze_test_files_ast(self) -> Dict[str, Any]:
        """Analyze test files using tree-sitter AST parsing"""
        # Dynamically find directories that contain test files
        directories = self._scan_directories()
        test_dirs = []
        
        # Look for directories that likely contain tests
        for dir_name, dir_info in directories.items():
            if dir_info.get('exists') and dir_info.get('count', 0) > 0:
                files = dir_info.get('files', [])
                # Check if directory has test files
                if any('spec' in f.lower() or 'test' in f.lower() for f in files):
                    test_dirs.append(dir_name)
        
        test_analysis = {
            'exists': len(test_dirs) > 0,
            'files': [],
            'describe_blocks': [],
            'test_patterns': {},
            'imports': [],
            'directories_scanned': test_dirs
        }
        
        for dir_name in test_dirs:
            dir_path = self.project_path / dir_name
            if dir_path.exists():
                for test_file in dir_path.glob('**/*'):
                    if test_file.suffix in ['.js', '.ts', '.spec.js', '.spec.ts', '.test.js', '.test.ts'] and test_file.is_file():
                        try:
                            ast_data = self._parse_typescript_file(test_file)
                            if ast_data:
                                file_info = {
                                    'path': str(test_file.relative_to(self.project_path)),
                                    'name': test_file.stem,
                                    'describe_blocks': ast_data.get('describe_blocks', []),
                                    'test_cases': ast_data.get('test_cases', []),
                                    'imports': ast_data.get('imports', [])
                                }
                                
                                test_analysis['files'].append(file_info)
                                test_analysis['describe_blocks'].extend(file_info['describe_blocks'])
                                test_analysis['imports'].extend(file_info['imports'])
                                
                        except Exception as e:
                            print(f"⚠️ Could not analyze {test_file}: {e}")
        
        return test_analysis
    
    def _parse_typescript_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse TypeScript file using tree-sitter"""
        
        if not self.parser:
            return self._fallback_text_parsing(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read().encode('utf8')
            
            # Parse the file
            tree = self.parser.parse(source_code)
            root_node = tree.root_node
            
            result = {
                'classes': [],
                'imports': [],
                'describe_blocks': [],
                'test_cases': []
            }
            
            # Walk the AST
            self._extract_from_ast(root_node, source_code, result)
            
            return result
            
        except Exception as e:
            print(f"⚠️ Tree-sitter parsing failed for {file_path}: {e}")
            return self._fallback_text_parsing(file_path)
    
    def _extract_from_ast(self, node: 'Node', source_code: bytes, result: Dict[str, Any]):
        """Extract information from AST nodes"""
        
        # Extract class declarations
        if node.type == 'class_declaration':
            class_info = self._extract_class_info(node, source_code)
            if class_info:
                result['classes'].append(class_info)
        
        # Extract import statements
        elif node.type == 'import_statement':
            import_text = source_code[node.start_byte:node.end_byte].decode('utf8')
            result['imports'].append(import_text.strip())
        
        # Extract describe blocks
        elif node.type == 'call_expression':
            self._extract_test_calls(node, source_code, result)
        
        # Recursively process child nodes
        for child in node.children:
            self._extract_from_ast(child, source_code, result)
    
    def _extract_class_info(self, class_node: 'Node', source_code: bytes) -> Optional[Dict[str, Any]]:
        """Extract class information from AST node"""
        
        class_name = None
        methods = []
        
        for child in class_node.children:
            # Get class name
            if child.type == 'type_identifier':
                class_name = source_code[child.start_byte:child.end_byte].decode('utf8')
            
            # Get class body
            elif child.type == 'class_body':
                methods = self._extract_methods_from_class_body(child, source_code)
        
        if class_name:
            return {
                'name': class_name,
                'methods': methods
            }
        
        return None
    
    def _extract_methods_from_class_body(self, class_body_node: 'Node', source_code: bytes) -> List[Dict[str, Any]]:
        """Extract methods from class body AST node"""
        
        methods = []
        
        for child in class_body_node.children:
            if child.type == 'method_definition':
                method_info = self._extract_method_info(child, source_code)
                if method_info:
                    methods.append(method_info)
        
        return methods
    
    def _extract_method_info(self, method_node: 'Node', source_code: bytes) -> Optional[Dict[str, Any]]:
        """Extract method information from AST node"""
        
        method_name = None
        is_async = False
        selectors = []
        
        for child in method_node.children:
            # Check for async modifier
            if child.type == 'async':
                is_async = True
            
            # Get method name
            elif child.type == 'property_identifier':
                method_name = source_code[child.start_byte:child.end_byte].decode('utf8')
            
            # Extract selectors from method body
            elif child.type == 'statement_block':
                selectors = self._extract_selectors_from_body(child, source_code)
        
        if method_name and method_name != 'constructor':
            return {
                'name': method_name,
                'type': 'async' if is_async else 'sync',
                'selectors': selectors
            }
        
        return None
    
    def _extract_selectors_from_body(self, body_node: 'Node', source_code: bytes) -> List[str]:
        """Extract Playwright selectors from method body - including CSS selectors"""
        
        selectors = []
        
        def find_selectors(node):
            # Look for call expressions that might be selectors
            if node.type == 'call_expression':
                # Get the function being called
                if node.children:
                    member_expr = node.children[0]
                    if member_expr.type == 'member_expression':
                        # Check if it's a Playwright selector method (including CSS)
                        method_text = source_code[member_expr.start_byte:member_expr.end_byte].decode('utf8')
                        playwright_methods = ['getByRole', 'getByText', 'getByLabel', 'getByTestId', 'locator', 'querySelector', 'querySelectorAll']
                        if any(selector in method_text for selector in playwright_methods):
                            full_call = source_code[node.start_byte:node.end_byte].decode('utf8')
                            selectors.append(full_call)
            
            # Recursively search child nodes
            for child in node.children:
                find_selectors(child)
        
        find_selectors(body_node)
        return selectors
    
    def _extract_test_calls(self, call_node: 'Node', source_code: bytes, result: Dict[str, Any]):
        """Extract describe and test calls from AST"""
        
        if call_node.children:
            function_node = call_node.children[0]
            
            if function_node.type == 'identifier':
                function_name = source_code[function_node.start_byte:function_node.end_byte].decode('utf8')
                
                # Look for describe or test calls
                if function_name in ['describe', 'test', 'it']:
                    # Get the first string argument
                    for child in call_node.children:
                        if child.type == 'arguments':
                            for arg in child.children:
                                if arg.type == 'string':
                                    # Remove quotes from string
                                    text = source_code[arg.start_byte:arg.end_byte].decode('utf8')
                                    text = text.strip('"\'`')
                                    
                                    if function_name == 'describe':
                                        result['describe_blocks'].append(text)
                                    elif function_name in ['test', 'it']:
                                        result['test_cases'].append(text)
                                    break
                            break
    
    def _fallback_text_parsing(self, file_path: Path) -> Dict[str, Any]:
        """Fallback to simple text parsing if tree-sitter fails"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            
            result = {
                'classes': [],
                'imports': re.findall(r'import\s+.+\s+from\s+[\'"`][^\'"`]+[\'"`]', content),
                'describe_blocks': re.findall(r'describe\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content),
                'test_cases': re.findall(r'test\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content)
            }
            
            # Extract classes with basic regex
            class_matches = re.findall(r'export\s+class\s+(\w+)', content)
            for class_name in class_matches:
                # Try to extract methods for this class
                class_pattern = rf'export\s+class\s+{class_name}.*?\{{(.*?)(?=\nexport|\nclass|\Z)'
                class_match = re.search(class_pattern, content, re.DOTALL)
                
                methods = []
                if class_match:
                    class_body = class_match.group(1)
                    # Extract method names
                    method_matches = re.findall(r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\s*\{', class_body)
                    for method_name in method_matches:
                        if method_name != 'constructor':
                            methods.append({
                                'name': method_name,
                                'type': 'unknown',
                                'selectors': []
                            })
                
                result['classes'].append({
                    'name': class_name,
                    'methods': methods
                })
            
            return result
            
        except Exception as e:
            print(f"⚠️ Fallback parsing failed for {file_path}: {e}")
            return {'classes': [], 'imports': [], 'describe_blocks': [], 'test_cases': []}
    
    def _extract_patterns(self) -> Dict[str, Any]:
        """Extract common patterns from the codebase"""
        patterns = {
            'naming_convention': self._detect_naming_convention(),
            'import_style': self._detect_import_style(),
            'selector_strategy': self._detect_selector_strategy(),
            'test_structure': self._detect_test_structure()
        }
        
        return patterns
    
    def _detect_naming_convention(self) -> Dict[str, str]:
        """Detect naming conventions by analyzing actual files - avoid recursion"""
        conventions = {
            'page_classes': 'Unknown',
            'methods': 'Unknown', 
            'files': 'Unknown',
            'test_files': 'Unknown'
        }
        
        try:
            # Get basic data without calling analyze_project_structure (to avoid recursion)
            directories = self._scan_directories()
            
            # Get page classes directly
            page_classes = []
            page_methods = []
            
            # Find page directories
            for dir_name, dir_info in directories.items():
                if dir_info.get('exists') and dir_info.get('count', 0) > 0:
                    files = dir_info.get('files', [])
                    if any('page' in f.lower() or 'Page' in f for f in files):
                        # This is likely a page directory
                        dir_path = self.project_path / dir_name
                        for page_file in dir_path.glob('**/*'):
                            if page_file.suffix in ['.js', '.ts', '.jsx', '.tsx'] and page_file.is_file():
                                try:
                                    ast_data = self._parse_typescript_file(page_file)
                                    if ast_data:
                                        for class_info in ast_data.get('classes', []):
                                            page_classes.append(class_info['name'])
                                            for method in class_info.get('methods', []):
                                                page_methods.append(method['name'])
                                except:
                                    pass
            
            # Analyze class naming pattern
            if page_classes:
                if all(name[0].isupper() and any(c.isupper() for c in name[1:]) for name in page_classes):
                    conventions['page_classes'] = 'PascalCase'
                elif all(name.islower() for name in page_classes):
                    conventions['page_classes'] = 'lowercase'
                elif all('_' in name for name in page_classes):
                    conventions['page_classes'] = 'snake_case'
            
            # Analyze method naming pattern
            if page_methods:
                if all(method[0].islower() and not '_' in method for method in page_methods):
                    conventions['methods'] = 'camelCase'
                elif all('_' in method for method in page_methods):
                    conventions['methods'] = 'snake_case'
            
            # Analyze file names
            all_files = []
            for dir_info in directories.values():
                all_files.extend([Path(f).stem for f in dir_info.get('files', [])])
            
            if all_files:
                # Detect file naming pattern
                kebab_count = sum(1 for f in all_files if '-' in f and len(f) > 5)
                snake_count = sum(1 for f in all_files if '_' in f and len(f) > 5)
                pascal_count = sum(1 for f in all_files if f[0].isupper() and len(f) > 3)
                
                if kebab_count > snake_count and kebab_count > pascal_count:
                    conventions['files'] = 'kebab-case'
                elif snake_count > kebab_count and snake_count > pascal_count:
                    conventions['files'] = 'snake_case'
                elif pascal_count > 0:
                    conventions['files'] = 'PascalCase'
                else:
                    conventions['files'] = 'camelCase'
            
            # Analyze test file patterns
            test_files = []
            for dir_name, dir_info in directories.items():
                if dir_info.get('exists'):
                    files = dir_info.get('files', [])
                    test_files.extend([f for f in files if 'spec' in f.lower() or 'test' in f.lower()])
            
            if test_files:
                if any('.spec.ts' in f for f in test_files):
                    conventions['test_files'] = 'name.spec.ts'
                elif any('.spec.js' in f for f in test_files):
                    conventions['test_files'] = 'name.spec.js'
                elif any('.test.' in f for f in test_files):
                    conventions['test_files'] = 'name.test.js'
            
        except Exception as e:
            print(f"⚠️ Error detecting naming conventions: {e}")
        
        return conventions
    
    def _detect_import_style(self) -> Dict[str, str]:
        """Detect import statement patterns"""
        return {
            'page_imports': "from '../pages/PageName'",
            'test_imports': "from '@playwright/test'",
            'relative_paths': True
        }
    
    def _detect_selector_strategy(self) -> Dict[str, Any]:
        """Detect preferred selector strategy"""
        return {
            'primary': 'getByRole',
            'fallback': 'getByText',
            'test_ids': False,
            'css_selectors': False
        }
    
    def _detect_test_structure(self) -> Dict[str, Any]:
        """Detect test structure patterns"""
        return {
            'uses_describe': True,
            'uses_before_each': True,
            'fixture_style': 'standard'
        }
    
    def _find_reusable_methods(self) -> Dict[str, List[str]]:
        """Find methods that can be reused for new tests"""
        # This would analyze actual methods found
        return {
            'authentication': ['login', 'logout'],
            'navigation': ['navigate', 'goto'],
            'crud': ['create', 'edit', 'delete'],
            'form': ['fill', 'submit'],
            'verification': ['verify', 'assert']
        }
    
    def make_integration_decisions(self, test_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make decisions about where to place new test and what to reuse"""
        analysis = self.analyze_project_structure()
        
        # Extract domain from test request
        domain = self._extract_domain_from_request(test_request)
        
        # Make placement decisions
        decisions = {
            'spec_decision': self._decide_spec_placement(domain, analysis),
            'page_decision': self._decide_page_placement(domain, analysis),
            'method_reuse': self._decide_method_reuse(test_request, analysis),
            'selector_strategy': analysis['patterns']['selector_strategy']
        }
        
        return decisions
    
    def _extract_domain_from_request(self, test_request: Dict[str, Any]) -> str:
        """Extract functional domain from test request"""
        steps = test_request.get('steps', [])
        title = test_request.get('title', '')
        
        # Enhanced domain detection based on your actual project structure
        domain_keywords = {
            'users': ['user', 'account', 'profile'],
            'auth': ['login', 'logout', 'signin', 'authentication'],
            'environment': ['environment', 'env', 'workspace'],
            'applications': ['application', 'app'],
            'groups': ['group', 'groups']
        }
        
        content = f"{title} {' '.join(steps)}".lower()
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in content for keyword in keywords):
                return domain
        
        return 'general'
    
    def _decide_spec_placement(self, domain: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Decide where to place the new test spec"""
        existing_files = [f['name'] for f in analysis['tests']['files']]
        
        # Check exact matches first
        exact_matches = [f for f in existing_files if domain in f.lower()]
        if exact_matches:
            return {'action': 'append', 'target': f"{exact_matches[0]}.ts"}
        
        # Check for management files
        management_pattern = f"{domain}-management"
        mgmt_matches = [f for f in existing_files if management_pattern in f.lower()]
        if mgmt_matches:
            return {'action': 'append', 'target': f"{mgmt_matches[0]}.ts"}
        
        return {'action': 'create', 'target': f"{domain}.spec.ts"}
    
    def _decide_page_placement(self, domain: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Decide page object placement"""
        existing_classes = analysis['pages']['classes']
        
        # Check for exact domain page
        domain_page = f"{domain.capitalize()}Page"
        domain_page_alt = f"{domain.capitalize()}sPage"  # plural
        
        if domain_page in existing_classes:
            return {'action': 'extend', 'target': domain_page}
        elif domain_page_alt in existing_classes:
            return {'action': 'extend', 'target': domain_page_alt}
        else:
            return {'action': 'create', 'target': domain_page}
    
    def _decide_method_reuse(self, test_request: Dict[str, Any], analysis: Dict[str, Any]) -> List[str]:
        """Decide which existing methods can be reused"""
        reusable = []
        
        steps = ' '.join(test_request.get('steps', [])).lower()
        
        # Check each page's methods for reusability
        for class_name, methods in analysis['pages']['methods'].items():
            for method in methods:
                method_name = method['name'].lower()
                
                # Login detection
                if ('login' in steps or 'signin' in steps) and 'login' in method_name:
                    reusable.append(f"{class_name}.{method['name']}")
                
                # Navigation detection
                if 'navigate' in steps and 'navigate' in method_name:
                    reusable.append(f"{class_name}.{method['name']}")
        
        return reusable

def create_project_intelligence(project_path: str) -> ProjectIntelligence:
    """Factory function to create ProjectIntelligence instance"""
    return ProjectIntelligence(project_path)