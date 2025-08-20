from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base

class DocumentOutlineItem(Base):
    """
    SQLAlchemy model for the 'document_outline_items' table.

    This class defines the database schema for storing individual items
    of a document's outline, such as headings and subheadings. Each item is
    linked to a parent document.
    """
    __tablename__ = "document_outline_items"

    # The unique identifier for the outline item, serves as the primary key.
    section_id = Column(String, primary_key=True, index=True)
    
    # The foreign key linking this outline item to a document.
    # `ondelete="CASCADE"` ensures that if a document is deleted,
    # all of its outline items are also deleted.
    documentId = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # The heading level of the outline item (e.g., "H1", "H2").
    level = Column(String, nullable=True)
    
    # The text content of the outline item (the heading itself).
    text = Column(Text, nullable=True)
    
    # The full text content of the section associated with this outline item.
    section_text = Column(Text, nullable=True) # Added for full section content
    
    # Additional data or notes for the item, often used by the frontend.
    annotation = Column(Text, nullable=True)
    
    # The page number in the document where this outline item appears.
    page = Column(Integer, nullable=True)

    # --- Relationships ---
    # Defines the many-to-one relationship from DocumentOutlineItem to Document.
    # `back_populates` links this to the `outline_items` relationship in the
    # Document model.
    document = relationship("Document", back_populates="outline_items")
