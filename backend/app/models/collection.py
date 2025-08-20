from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class Collection(Base):
    """
    SQLAlchemy model for the 'collections' table.
    
    This class defines the database schema for storing collections. Each collection
    acts as a container for related documents.
    """
    __tablename__ = "collections"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True) 
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    updatedAt = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    latestInsightId = Column(String, nullable=True)
    latestPodcastId = Column(String, nullable=True)

    documents = relationship("Document", back_populates="collection", cascade="all, delete-orphan")
