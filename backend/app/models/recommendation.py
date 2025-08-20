from sqlalchemy import Column, String, Text, DateTime, func, Enum
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.schemas.recommendation import RecommendationType # Import the RecommendationType enum

class Recommendation(Base):
    """
    SQLAlchemy model for the 'recommendations' table.
    """
    __tablename__ = "recommendations"
    __table_args__ = {'extend_existing': True}

    recommendation_id = Column(String, primary_key=True, index=True)
    collection_id = Column(String, index=True, nullable=False)
    user_selection_text = Column(Text, nullable=True)
    spanned_section_ids = Column(Text, nullable=True)
    list_of_doc_ids_used = Column(Text, nullable=True)
    latest_podcast_id = Column(String, nullable=True, index=True)
    latest_insight_id = Column(String, nullable=True, index=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    recommendation_type = Column(Enum(RecommendationType), nullable=False, default=RecommendationType.TEXT)

    items = relationship("RecommendationItem", back_populates="recommendation", cascade="all, delete-orphan")
