from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base

class RecommendationItem(Base):
    """
    SQLAlchemy model for the 'recommendation_items' table.

    This class defines the database schema for storing an individual snippet
    that was part of a recommendation event. Each item is linked to a parent
    Recommendation record.
    """
    __tablename__ = "recommendation_items"
    __table_args__ = {'extend_existing': True}

    # The unique identifier for this single recommendation item.
    item_id = Column(String, primary_key=True, index=True)
    
    # The foreign key linking this item to its parent recommendation event.
    # `ondelete="CASCADE"` ensures that if a recommendation record is deleted,
    # all of its items are also deleted.
    recommendation_id = Column(String, ForeignKey("recommendations.recommendation_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # --- Metadata for the snippet ---
    document_title = Column(String, nullable=True) # Renamed from document_name
    doc_id = Column(String, index=True, nullable=False)
    section_title = Column(Text, nullable=True)
    section_id = Column(String, index=True, nullable=False)
    page_number = Column(Integer, nullable=True)
    
    # The precise, LLM-extracted snippet text to be highlighted.
    snippet_text = Column(Text, nullable=False)
    
    # A short, LLM-generated explanation of why this snippet is relevant to the user's selection.
    snippet_explanation = Column(Text, nullable=True)
    
    # The annotation data (bounding box coordinates) for the snippet.
    annotation = Column(Text, nullable=True)
    quad_points = Column(Text, nullable=True) # Store quad_points as JSON string

    # --- Relationships ---
    # Defines the many-to-one relationship from RecommendationItem to Recommendation.
    # `back_populates` links this to the `items` relationship in the
    # Recommendation model.
    recommendation = relationship("Recommendation", back_populates="items")
