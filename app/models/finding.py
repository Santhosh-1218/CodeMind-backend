import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base

class Finding(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("reviews.id"), nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False) # Security, Bug, Quality, Performance, Architecture
    severity = Column(String, nullable=False) # Critical, High, Medium, Low, Info
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)
    snippet = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True) # Why it matters
    fix_recommendation = Column(Text, nullable=False)
    confidence = Column(Integer, default=90) # 0 to 100
    evidence = Column(Text, nullable=True) # JSON list of evidence points
    memory_influenced = Column(Boolean, default=False)
    hindsight_memory_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    review = relationship("Review", back_populates="findings")
