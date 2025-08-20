from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.db.session import Base

class Document(Base):
    """
    SQLAlchemy model for the 'documents' table.

    This class defines the database schema for storing metadata about each
    document. Each document is linked to a parent collection.
    """
    __tablename__ = "documents"

    # The unique identifier for the document.
    id = Column(String, primary_key=True, index=True)
    
    # The foreign key linking this document to a collection.
    # `ondelete="CASCADE"` ensures that if a collection is deleted,
    # all of its documents are also deleted from the database.
    collectionId = Column(String, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    
    # The original filename of the document.
    docName = Column(String, nullable=False)
    
    # The size of the document in kilobytes.
    docSizeKB = Column(Integer, nullable=True)
    
    # A user-editable title for the document.
    docTitle = Column(String, nullable=True)
    
    # The total number of pages in the document.
    total_pages = Column(Integer, nullable=True)
    
    # The MIME type of the document (e.g., "application/pdf").
    docType = Column(String, nullable=True)
    
    # The path or URL where the document file is stored.
    docUrl = Column(String, nullable=True)
    
    # A cached reference to the ID of the most recently generated insight.
    latestInsightId = Column(String, nullable=True)
    
    # A cached reference to the ID of the most recently generated podcast.
    latestPodcastId = Column(String, nullable=True)
    
    # The processing status of the document (e.g., "Pending", "Success", "Failed").
    isProcessed = Column(String, default="Pending", nullable=False)

    # Status of embedding creation (e.g., "Pending", "Success", "Failed").
    isEmbeddingCreated = Column(String, default="Pending", nullable=False)

    # Timestamp for when the document was created.
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    
    # Timestamp for the last update to the document.
    # It also has a server_default to set the initial value on creation.
    updatedAt = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    # Defines the many-to-one relationship from Document to Collection.
    # `back_populates` links this to the `documents` relationship in the
    # Collection model.
    collection = relationship("Collection", back_populates="documents")
    
    # Defines the one-to-many relationship from Document to DocumentOutlineItem.
    # This means one document can have many outline items.
    outline_items = relationship("DocumentOutlineItem", back_populates="document", cascade="all, delete-orphan")
