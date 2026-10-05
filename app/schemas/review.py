from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ReviewCreateGitHub(BaseModel):
    repo_url: str

class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: str
    severity: str
    file_path: str
    line_number: Optional[int] = None
    line_end: Optional[int] = None
    snippet: Optional[str] = None
    description: str
    rationale: Optional[str] = None
    fix_recommendation: str
    confidence: int = 90
    evidence: List[str] = []
    memory_influenced: bool = False
    hindsight_memory_text: Optional[str] = None
    owasp_category: Optional[str] = None
    cwe_id: Optional[str] = None
    status: str = "open"
    assigned_to: Optional[str] = None

class ReviewFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    path: str
    language: str
    content: str
    size: int

class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    project_name: str
    repo_url: Optional[str] = None
    source_type: str
    status: str
    status_message: str
    overall_score: float = 85.0
    quality_score: float
    security_score: float
    reliability_score: float = 85.0
    maintainability_score: float
    summary: Optional[str] = None
    languages: List[str] = []
    file_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int = 0
    hindsight_memories_recalled: int
    hindsight_learnings_retained: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    findings: List[FindingResponse] = []
    files: List[ReviewFileResponse] = []

class ReviewStatusResponse(BaseModel):
    id: str
    status: str
    status_message: str
    quality_score: float
    security_score: float
    maintainability_score: float
    file_count: int
    completed_at: Optional[datetime] = None

class UpdateFindingStatusRequest(BaseModel):
    status: Optional[str] = None # open, in_progress, resolved, false_positive
    assigned_to: Optional[str] = None
