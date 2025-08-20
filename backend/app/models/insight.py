from sqlalchemy import Column, String, DateTime, func, JSON
from sqlalchemy.orm import relationship

from app.db.session import Base

class Insight(Base):
    """
    SQLAlchemy model for the 'insights' table.

    This class defines the database schema for storing generated insights.
    An insight can be related to either a document, collection, or recommendation.
    """
    __tablename__ = "insights"

    # The unique identifier for the insight.
    insightId = Column(String, primary_key=True, index=True)
    
    # The type of the source entity ('document', 'collection', or 'recommendation').
    sourceType = Column(String, nullable=False, index=True)
    
    # The ID of the source entity (e.g., a document ID, collection ID, or recommendation ID).
    sourceId = Column(String, nullable=False, index=True)
    
    # The actual structured insight content, stored as JSON.
    # This will be a list of dictionaries: [ { "type": "key_insight", "data": "...", "priority": 1 } ]
    insights_data = Column(JSON, nullable=False)
    
    # Timestamp for when the insight was generated.
    generatedAt = Column(DateTime(timezone=True), server_default=func.now())
