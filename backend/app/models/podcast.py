from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.types import JSON # Using generic JSON type for SQLite compatibility
from sqlalchemy.orm import relationship

from app.db.session import Base

class Podcast(Base):
    """
    SQLAlchemy model for the 'podcasts' table.

    This class defines the database schema for storing generated audio overviews
    (podcasts). A podcast can be related to either a document or a
    recommendation batch, handled via a polymorphic relationship.
    """
    __tablename__ = "podcasts"

    podcastId = Column(String, primary_key=True, index=True)
    sourceType = Column(String, nullable=False, index=True)
    sourceId = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")
    audioUrl = Column(String, nullable=True)
    transcript = Column(JSON, nullable=True) # Changed to JSON to store list of dicts for SQLite
    generatedAt = Column(DateTime(timezone=True), server_default=func.now())
    shortDescription = Column(String(255), nullable=True)
    durationSeconds = Column(Integer, nullable=True)
