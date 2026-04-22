from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class SpeakerMapping(Base):
    __tablename__ = "speaker_mappings"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    speaker_label = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)

    meeting = relationship("Meeting", back_populates="speaker_mappings")

