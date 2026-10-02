from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class MemoryItem(BaseModel):
    id: str
    text: str
    type: str
    context: Optional[str] = None
    created_at: Optional[str] = None

class RecurringIssueItem(BaseModel):
    category: str
    title: str
    count: int
    severity: str
    description: str

class LearnedPreferenceItem(BaseModel):
    category: str
    preference: str
    confidence: float
    example: str

class LearningTimelineItem(BaseModel):
    date: str
    project_name: str
    quality_score: float
    security_score: float
    memories_recalled: int
    learnings_retained: int

class LearningStatsResponse(BaseModel):
    total_memories: int
    total_reviews_analyzed: int
    recurring_issues: List[RecurringIssueItem]
    learned_preferences: List[LearnedPreferenceItem]
    timeline: List[LearningTimelineItem]
    recent_memories: List[MemoryItem]
