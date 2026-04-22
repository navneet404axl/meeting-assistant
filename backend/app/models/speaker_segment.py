from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class SpeakerSegment(Base):
    __tablename__ = "speaker_segments"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    speaker_label = Column(String, nullable=False, index=True)
    start = Column(Float, nullable=False)
    end = Column(Float, nullable=False)

    meeting = relationship("Meeting", back_populates="speaker_segments")

