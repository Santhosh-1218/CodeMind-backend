import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from app.db.database import Base

class ReviewFile(Base):
    __tablename__ = "review_files"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("reviews.id"), nullable=False)
    path = Column(String, nullable=False)
    language = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    size = Column(Integer, default=0)

    review = relationship("Review", back_populates="files")
