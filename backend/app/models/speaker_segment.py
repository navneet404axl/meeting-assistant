from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.meeting import Meeting


class SpeakerSegment(Base):
    __tablename__ = "speaker_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False, index=True)
    speaker_label: Mapped[str] = mapped_column(nullable=False, index=True)
    start: Mapped[float] = mapped_column(nullable=False)
    end: Mapped[float] = mapped_column(nullable=False)

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="speaker_segments")
