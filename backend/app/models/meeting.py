from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.db.database import Base

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")  # queued|processing|done|failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())