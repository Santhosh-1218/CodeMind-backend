import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Text
from sqlalchemy.orm import relationship
from app.db.database import Base

class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="Queued") # Queued, Downloading, Extracting, Files Discovered, Static Analysis, Recall Hindsight Memory, AI Reasoning, Saving Review, Retaining Learning, Completed, Failed
    status_message = Column(String, default="Review initialized...")
    quality_score = Column(Float, default=0.0)
    security_score = Column(Float, default=0.0)
    maintainability_score = Column(Float, default=0.0)
    summary = Column(Text, nullable=True)
    languages = Column(String, nullable=True) # JSON list string e.g. ["Python", "JavaScript"]
    file_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    hindsight_memories_recalled = Column(Integer, default=0)
    hindsight_learnings_retained = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="reviews")
    project = relationship("Project", back_populates="reviews")
    findings = relationship("Finding", back_populates="review", cascade="all, delete-orphan")
    files = relationship("ReviewFile", back_populates="review", cascade="all, delete-orphan")
