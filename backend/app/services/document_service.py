import uuid
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session, joinedload
from fastapi import UploadFile, HTTPException

# Import schemas and models
from app.models.document import Document # Import SQLAlchemy Document model
from app.models.collection import Collection # Import SQLAlchemy Collection model
from app.schemas.document_outline_item import DocumentOutlineItem # This is a Pydantic schema
from app.schemas.collection import CollectionCreate # This is a Pydantic schema
from app.schemas.document import ProcessingStatus # Import ProcessingStatus from Pydantic schema

# Import services and dependencies
from app.services.storage_service import StorageService, get_storage_service
from app.services.collection_service import CollectionService
from app.core.pdf_parser import HybridPDFOutlineExtractor

# Configure logger for this module
logger = logging.getLogger(__name__)

class DocumentService:
    """
    A service class containing the business logic for document operations.

    This service handles the lifecycle of documents, including uploading,
    parsing, storing metadata, and managing their processing status.
    It interacts with the database, storage service, and PDF parsing utilities.
    """

    def _parse_and_store_document_outline(
        self,
        db: Session,
        document_id: str,
        file_path: str
    ) -> Optional[Document]:
        """
        Private helper to parse a single PDF document and save its metadata and outline
        to the database. This function encapsulates the synchronous PDF processing logic.

        Args:
            db (Session): The SQLAlchemy database session.
            document_id (str): The unique identifier of the document being processed.
            file_path (str): The file system path to the PDF document.

        Returns:
            Optional[Document]: The updated SQLAlchemy Document object with parsed data,
                                or None if the document was not found in the database.

        Raises:
            Exception: If an error occurs during PDF parsing or database operations.
        """
        logger.debug(f"DocumentService: _parse_and_store_document_outline: Starting for document {document_id}, file: {file_path}")
        parser = HybridPDFOutlineExtractor()
        try:
            db_doc = db.query(Document).filter(Document.id == document_id).first()
            if not db_doc:
                logger.error(f"DocumentService: Document {document_id} not found during parsing.")
                return None

            parsed_data = parser.process_pdf(Path(file_path))
            logger.debug(f"DocumentService: Parsed data for {document_id}: {parsed_data.keys()}")
            logger.debug(f"DocumentService: Outline items found by parser: {len(parsed_data.get('outline', []))}")
            
            db_doc.docTitle = parsed_data.get("title", db_doc.docName)
            db_doc.total_pages = parsed_data.get("total_pages")
            
            for item_data in parsed_data.get("outline", []):
                db_outline_item = DocumentOutlineItem(
                    section_id=item_data.get("section_id"),
                    documentId=document_id,
                    level=item_data.get("level"),
                    text=item_data.get("text"),
                    section_text=item_data.get("section_text"),
                    annotation=item_data.get("annotation"),
                    page=item_data.get("page")
                )
                db.add(db_outline_item)
                db_doc.outline_items.append(db_outline_item)
                logger.debug(f"DocumentService: Adding outline item: {item_data.get('text')[:50]}... Section text length: {len(item_data.get('section_text', ''))}")
            
            db.commit()
            db.refresh(db_doc)
            
            if hasattr(db_doc, 'outline_items') and db_doc.outline_items:
                db_doc._outline_data_for_pydantic = [
                    {
                        "level": item.level,
                        "section_id": item.section_id,
                        "documentId": item.documentId,
                        "text": item.text,
                        "annotation": item.annotation,
                        "page": item.page
                    }
                    for item in db_doc.outline_items
                ]
            else:
                db_doc._outline_data_for_pydantic = []

            logger.debug(f"DocumentService: Successfully processed document: {document_id}. Stored {len(db_doc._outline_data_for_pydantic)} items for Pydantic.")
            return db_doc

        except Exception as e:
            logger.error(f"DocumentService: Failed to process document {document_id}. Error: {e}", exc_info=True)
            db.rollback()
            raise e

    def create_documents_from_upload(
        self, 
        db: Session, 
        files: List[UploadFile], 
        storage_service: StorageService,
        collection_service: CollectionService,
        collection_id: Optional[str] = None
    ) -> List[Document]:
        """
        Handles the bulk upload and synchronous initial processing of documents.
        It saves files to storage, creates initial document records in the database,
        and then synchronously parses the PDF outline and metadata.

        Args:
            db (Session): The SQLAlchemy database session.
            files (List[UploadFile]): A list of uploaded files from the FastAPI endpoint.
            storage_service (StorageService): The storage service dependency for saving files.
            collection_service (CollectionService): The collection service dependency for managing collections.
            collection_id (Optional[str]): The ID of the collection to upload documents to.
                                           If None, documents are added to a default collection.

        Returns:
            List[Document]: A list of SQLAlchemy Document objects that have been processed.

        Raises:
            HTTPException: 404 Not Found if a specified collection_id does not exist.
        """
        logger.debug(f"DocumentService: Starting document upload and processing for {len(files)} files.")
        if not collection_id:
            default_collection_name = "Default Uploads"
            db_collection = db.query(Collection).filter(Collection.name == default_collection_name).first()
            if not db_collection:
                logger.info(f"DocumentService: Default collection '{default_collection_name}' not found, creating it.")
                db_collection = collection_service.create_collection(
                    db, CollectionCreate(name=default_collection_name, description="Automatically created for default uploads.")
                )
            collection_id = db_collection.id
            logger.debug(f"DocumentService: Using collection ID: {collection_id} (default or existing).")
        else:
            db_collection = collection_service.get_collection(db, collection_id)
            if not db_collection:
                logger.warning(f"DocumentService: Collection with id {collection_id} not found for upload.")
                raise HTTPException(status_code=404, detail=f"Collection with id {collection_id} not found.")
            logger.debug(f"DocumentService: Using provided collection ID: {collection_id}.")

        processed_documents = []
        for file in files:
            logger.debug(f"DocumentService: Processing file: {file.filename}")
            relative_path = storage_service.save_uploaded_file(file=file, collection_id=collection_id)
            absolute_path = storage_service.get_absolute_path(relative_path)
            doc_url = storage_service.get_file_url(relative_path)
            logger.debug(f"DocumentService: File saved to: {absolute_path}, URL: {doc_url}")
            
            doc_id = f"doc_{uuid.uuid4().hex}"
            db_doc = Document(
                id=doc_id,
                collectionId=collection_id,
                docName=file.filename,
                docSizeKB=file.size // 1024 if file.size else None,
                docType=file.content_type,
                docUrl=doc_url
            )
            db.add(db_doc)
            db.commit()
            logger.debug(f"DocumentService: Initial document record created for {doc_id}.")
            
            fully_processed_db_doc = self._parse_and_store_document_outline(db=db, document_id=doc_id, file_path=str(absolute_path))
            
            if not fully_processed_db_doc:
                logger.error(f"DocumentService: Document {doc_id} failed outline parsing, skipping.")
                continue

            if fully_processed_db_doc.total_pages is not None:
                db_doc.total_pages = fully_processed_db_doc.total_pages 
                logger.debug(f"DocumentService: Document {fully_processed_db_doc.id} total_pages set to: {fully_processed_db_doc.total_pages}")
            else:
                logger.debug(f"DocumentService: Document {fully_processed_db_doc.id} total_pages is None after parsing.")
            
            fully_processed_db_doc.isProcessed = ProcessingStatus.SUCCESS
            fully_processed_db_doc.isEmbeddingCreated = ProcessingStatus.PENDING
            db.add(fully_processed_db_doc)
            db.commit()
            db.refresh(fully_processed_db_doc)

            logger.debug(f"DocumentService: Document {fully_processed_db_doc.id} isProcessed after final refresh: {fully_processed_db_doc.isProcessed}, total_pages after final refresh: {fully_processed_db_doc.total_pages}, outline_items count: {len(fully_processed_db_doc.outline_items) if hasattr(fully_processed_db_doc, 'outline_items') else 'N/A'}")
            processed_documents.append(fully_processed_db_doc)

        if processed_documents:
            logger.debug(f"DocumentService: Returning processed_documents. First doc isProcessed: {processed_documents[0].isProcessed}, outline_items count: {len(processed_documents[0].outline_items)}")
            
        return processed_documents

    def get_document(self, db: Session, document_id: str) -> Optional[Document]:
        """
        Retrieves a single document by its ID, eagerly loading its outline items.

        Args:
            db (Session): The SQLAlchemy database session.
            document_id (str): The ID of the document to retrieve.

        Returns:
            Optional[Document]: The SQLAlchemy Document object if found, otherwise None.
        """
        logger.debug(f"DocumentService: Attempting to retrieve document with ID: {document_id}")
        db_doc = db.query(Document).options(joinedload(Document.outline_items)).filter(Document.id == document_id).first()
        if db_doc:
            _ = [item for item in db_doc.outline_items] # Force loading
            logger.debug(f"DocumentService: Found document {document_id}.")
        else:
            logger.debug(f"DocumentService: Document {document_id} not found.")
        return db_doc

    def get_documents_by_collection(self, db: Session, collection_id: str) -> List[Document]:
        """
        Retrieves all documents belonging to a specific collection, eagerly loading their outline items.

        Args:
            db (Session): The SQLAlchemy database session.
            collection_id (str): The ID of the collection whose documents are to be retrieved.

        Returns:
            List[Document]: A list of SQLAlchemy Document objects within the specified collection.
        """
        logger.debug(f"DocumentService: Attempting to retrieve documents for collection ID: {collection_id}")
        db_docs = db.query(Document).options(joinedload(Document.outline_items)).filter(Document.collectionId == collection_id).all()
        for doc in db_docs:
            _ = [item for item in doc.outline_items] # Force loading
        logger.debug(f"DocumentService: Retrieved {len(db_docs)} documents for collection {collection_id}.")
        return db_docs

    def delete_document(self, db: Session, document_id: str) -> Optional[Document]:
        """
        Deletes a document from the database and storage, then triggers a synchronous refresh
        of the embeddings for the associated collection.

        Args:
            db (Session): The SQLAlchemy database session.
            document_id (str): The ID of the document to delete.

        Returns:
            Optional[Document]: The deleted SQLAlchemy Document object if found, otherwise None.
        """
        logger.debug(f"DocumentService: Attempting to delete document with ID: {document_id}")
        db_doc = self.get_document(db, document_id)
        if not db_doc:
            logger.debug(f"DocumentService: Document {document_id} not found for deletion.")
            return None
        
        # Extract relative path from document URL
        from app.core.config import settings
        base_url = f"{settings.BASE_URL}/storage/"
        if db_doc.docUrl and db_doc.docUrl.startswith(base_url):
            relative_path = db_doc.docUrl[len(base_url):]
            try:
                storage_service = get_storage_service()
                storage_service.delete_uploaded_file(relative_path)
                logger.info(f"DocumentService: Deleted document file: {relative_path}")
            except Exception as e:
                logger.error(f"DocumentService: Failed to delete document file: {str(e)}")
                # Continue with DB deletion even if file deletion fails
        
        collection_id = db_doc.collectionId
        db.delete(db_doc)
        db.commit()
        logger.debug(f"DocumentService: Successfully deleted document {document_id} from database.")
        
        # Trigger a synchronous refresh of the embeddings for the collection
        # This import is intentionally placed here to break potential circular dependencies
        from app.services.recommender_service import get_recommender_service
        recommender_service = get_recommender_service()
        
        logger.debug(f"DocumentService: Triggering synchronous embedding refresh for collection {collection_id} after document deletion.")
        recommender_service.update_embeddings_for_collection(
            db=db, 
            storage_service=get_storage_service(), 
            collection_id=collection_id
        )
        logger.debug(f"DocumentService: Embedding refresh for collection {collection_id} completed.")
        
        return db_doc

# Create a single instance of the service
document_service = DocumentService()

def get_document_service():
    """
    Dependency function to provide the document service instance.
    """
    return document_service
