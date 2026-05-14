from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Text
from sqlalchemy.sql import func
from app.db.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.speaker_mapping import SpeakerMapping
    from app.models.speaker_segment import SpeakerSegment
    from app.models.transcript import TranscriptSegment

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str | None] = mapped_column(nullable=True)
    filename: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="queued")  # queued|processing|done|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        "TranscriptSegment",
        back_populates="meeting",
        cascade="all, delete-orphan"
    )
    speaker_segments: Mapped[list[SpeakerSegment]] = relationship(
        "SpeakerSegment",
        back_populates="meeting",
        cascade="all, delete-orphan"
    )
    speaker_mappings: Mapped[list[SpeakerMapping]] = relationship(
        "SpeakerMapping",
        back_populates="meeting",
        cascade="all, delete-orphan"
    )
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    decisions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_model_output: Mapped[str | None] = mapped_column(Text, nullable=True)
