from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.database import Base
from sqlalchemy.orm import relationship

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")  # queued|processing|done|failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    transcript_segments = relationship(
        "TranscriptSegment",
        back_populates="meeting",
        cascade="all, delete-orphan"
    )
    summary_text = Column(Text, nullable=True)
    decisions_json = Column(Text, nullable=True)
    action_items_json = Column(Text, nullable=True)
    raw_model_output = Column(Text, nullable=True)