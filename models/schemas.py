# models/schemas.py
"""
Pydantic models for Playwright test generation workflow
Designed to fit existing code patterns - Updated for Pydantic 2.11.7
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

class StructuredStep(BaseModel):
    """Azure DevOps structured step format"""
    step: int
    action: str
    expected: Optional[str] = ""

class TestCaseMetadata(BaseModel):
    """Metadata from different sources - matches azure_devops_client.py format"""
    work_item_id: Optional[str] = None
    work_item_type: Optional[str] = None
    work_item_url: Optional[str] = None
    state: Optional[str] = None
    assigned_to: Optional[str] = None
    area_path: Optional[str] = None
    iteration_path: Optional[str] = None

class TestCase(BaseModel):
    """Standardized test case - matches your existing dict structure"""
    id: str
    title: str
    steps: str
    expectedResults: str
    structured_steps: Optional[List[StructuredStep]] = []
    source: Optional[str] = None
    metadata: Optional[TestCaseMetadata] = None

    @field_validator('id')
    @classmethod
    def id_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Test case ID cannot be empty")
        return v.strip()

class POMFile(BaseModel):
    """Page Object file structure - matches extraction_utils expectations"""
    path: str
    content: str
    
    @field_validator('path')
    @classmethod
    def validate_pom_path(cls, v):
        if not v.startswith('pages/') or not v.endswith('.js'):
            raise ValueError("POM path must be 'pages/ClassName.js'")
        return v

class POMGeneratorResponse(BaseModel):
    """Response format for POM Generator - enforces JSON structure from prompts"""
    files: List[POMFile]
    
    @field_validator('files')
    @classmethod
    def must_have_files(cls, v):
        if not v:
            raise ValueError("Must generate at least one POM file")
        return v

class TestGeneratorResponse(BaseModel):
    """Response format for Test Generator"""
    test_file: str
    
    @field_validator('test_file')
    @classmethod
    def validate_test_content(cls, v):
        if not v or len(v.strip()) < 20:
            raise ValueError("Test file content cannot be empty")
        # Basic validation for Playwright test structure
        required = ['import', 'test(']
        if not all(req in v for req in required):
            raise ValueError("Test must contain imports and test() function")
        return v

class MCPLogEntry(BaseModel):
    """MCP execution log entry - matches your current structure"""
    tool: str
    args: Dict[str, Any]
    result: Dict[str, Any] 
    description: str
    is_verification: bool = False