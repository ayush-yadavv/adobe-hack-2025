from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.schemas.document_outline_item_pydantic import DocumentOutlineItemPydantic

class ProcessingStatus(str, Enum):
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"

class DocumentBase(BaseModel):
    docTitle: Optional[str] = Field(None, description="A user-editable title for the document.")

class DocumentCreate(DocumentBase):
    docUrl: str = Field(..., description="The URL of the document to be ingested.")

class DocumentUpdate(DocumentBase):
    pass

class DocumentInDB(DocumentBase):
    id: str = Field(..., description="The unique identifier for the document.")
    collectionId: str = Field(..., description="The ID of the collection this document belongs to.")
    docName: str = Field(..., description="The original filename of the document.")
    docSizeKB: Optional[int] = Field(None, description="The size of the document in kilobytes.")
    total_pages: Optional[int] = Field(None, description="The total number of pages in the document.")
    docType: Optional[str] = Field(None, description="The MIME type of the document.")
    docUrl: Optional[str] = Field(None, description="The URL where the document is stored.")
    createdAt: datetime = Field(..., description="The timestamp when the document was created.")
    updatedAt: Optional[datetime] = Field(None, description="The timestamp of the last update.")
    
    latestInsightId: Optional[str] = Field(None, description="ID of the latest insight generated for this document.")
    latestPodcastId: Optional[str] = Field(None, description="ID of the latest podcast generated for this document.")
    isProcessed: ProcessingStatus = Field(ProcessingStatus.PENDING, description="The processing status of the document.")
    isEmbeddingCreated: ProcessingStatus = Field(ProcessingStatus.PENDING, description="The status of embedding creation for the document.")

    outline: List[DocumentOutlineItemPydantic] = Field([], description="The structured outline of the document.")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "docTitle": "Example Document Title",
                "id": "doc_example_id_123",
                "collectionId": "collection_example_id_abc",
                "docName": "example_document.pdf",
                "docSizeKB": 1024,
                "total_pages": 5,
                "docType": "application/pdf",
                "docUrl": "storage/uploads/collection_example_id_abc/example_document.pdf",
                "createdAt": "2025-01-01T12:00:00",
                "updatedAt": "2025-01-01T12:00:00",
                "latestInsightId": None,
                "latestPodcastId": None,
                "isProcessed": "Success",
                "isEmbeddingCreated": "Pending",
                "outline": []
            }
        }
    )
