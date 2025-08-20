from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
import logging

# Configure logger for this module
logger = logging.getLogger(__name__)

# Import services, models, and dependencies
from app.services.document_service import get_document_service, DocumentService
from app.services.collection_service import get_collection_service, CollectionService
from app.services.storage_service import get_storage_service, StorageService
from app.schemas.document import DocumentInDB, ProcessingStatus
from app.models.document import Document 
from app.db.session import get_db
from app.schemas.document_outline_item_pydantic import DocumentOutlineItemPydantic
from app.schemas.collection import CollectionInDB
from pydantic import BaseModel, Field

# Create a new router for this module.
router = APIRouter()

# Define a custom response model for the default document upload endpoint
class UploadResponse(BaseModel):
    """
    Response model for document upload operations, including collection and document details.
    """
    collection: Optional[CollectionInDB] = Field(None, description="The collection details associated with the uploaded documents.")
    documents: List[DocumentInDB] = Field(..., description="List of uploaded document details.")

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload documents to a default collection",
    description="Handles the bulk upload of one or more documents. If no collection is specified, documents are added to a default collection. Document processing (e.g., embedding creation) is handled asynchronously in a background task. Returns the details of the collection and the newly created documents."
)
async def default_document_upload(
    *,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="List of files to upload."),
    document_service: DocumentService = Depends(get_document_service),
    collection_service: CollectionService = Depends(get_collection_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    """
    Handle bulk upload of documents to a default collection asynchronously.
    Documents will be processed in a background task.

    Args:
        db (Session): Database session dependency.
        background_tasks (BackgroundTasks): FastAPI's dependency for running background tasks.
        files (List[UploadFile]): The list of uploaded files.
        document_service (DocumentService): Dependency for document-related operations.
        collection_service (CollectionService): Dependency for collection-related operations.
        storage_service (StorageService): Dependency for storage-related operations.

    Returns:
        UploadResponse: An object containing the collection details and a list of uploaded document details.
    """
    logger.debug(f"API: Received default document upload request for {len(files)} files.")
    
    pending_docs = document_service.create_documents_from_upload(
        db=db,
        files=files,
        collection_id=None,
        storage_service=storage_service,
        collection_service=collection_service
    )
    logger.debug(f"API: Created {len(pending_docs)} pending documents. IDs: {[doc.id for doc in pending_docs]}")
    
    collection_id_for_response = pending_docs[0].collectionId if pending_docs else None

    collection_data = None
    if collection_id_for_response:
        collection_for_response = collection_service.get_collection(db=db, collection_id=collection_id_for_response)
        if not collection_for_response:
            logger.warning(f"API: Collection {collection_id_for_response} not found for response construction.")
        else:
            total_docs_in_collection = len(document_service.get_documents_by_collection(db=db, collection_id=collection_id_for_response))
            collection_data = CollectionInDB(
                id=collection_for_response.id,
                name=collection_for_response.name,
                description=collection_for_response.description,
                tags=collection_for_response.tags,
                createdAt=collection_for_response.createdAt,
                updatedAt=collection_for_response.updatedAt,
                total_docs=total_docs_in_collection,
                latestInsightId=collection_for_response.latestInsightId,
                latestPodcastId=collection_for_response.latestPodcastId
            )

    documents_for_response = []
    for doc in pending_docs:
        response_outline_pydantic = []
        if hasattr(doc, '_outline_data_for_pydantic') and doc._outline_data_for_pydantic:
            response_outline_pydantic = [
                DocumentOutlineItemPydantic.model_validate(item)
                for item in doc._outline_data_for_pydantic
            ]
        elif hasattr(doc, 'outline_items') and doc.outline_items:
            response_outline_pydantic = [
                DocumentOutlineItemPydantic.model_validate(item, from_attributes=True)
                for item in doc.outline_items
            ]

        documents_for_response.append(
            DocumentInDB(
                docTitle=doc.docTitle,
                id=doc.id,
                collectionId=doc.collectionId,
                docName=doc.docName,
                docSizeKB=doc.docSizeKB,
                total_pages=doc.total_pages,
                docType=doc.docType,
                docUrl=doc.docUrl,
                createdAt=doc.createdAt,
                updatedAt=doc.updatedAt,
                latestInsightId=doc.latestInsightId,
                latestPodcastId=doc.latestPodcastId,
                isProcessed=ProcessingStatus.SUCCESS,
                isEmbeddingCreated=ProcessingStatus.PENDING,
                outline=response_outline_pydantic
            )
        )
    if collection_id_for_response:
        from app.services.recommender_service import get_recommender_service
        recommender_service = get_recommender_service()
        background_tasks.add_task(
            recommender_service.update_embeddings_for_collection,
            db,
            storage_service,
            collection_id_for_response
        )
    logger.debug(f"API: Responding to default document upload with {len(documents_for_response)} documents.")
    return UploadResponse(collection=collection_data, documents=documents_for_response)

@router.post(
    "/collections/{collection_id}/documents/upload",
    response_model=List[DocumentInDB],
    status_code=status.HTTP_200_OK,
    summary="Upload documents to a specific collection",
    description="Handles the bulk upload of one or more documents to a specified collection. Document processing (e.g., embedding creation) is handled asynchronously in a background task. Returns a list of the newly created document details."
)
async def upload_documents_to_collection(
    *,
    db: Session = Depends(get_db),
    collection_id: str, # Removed Field(...)
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="List of files to upload."),
    document_service: DocumentService = Depends(get_document_service),
    collection_service: CollectionService = Depends(get_collection_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    """
    Handle bulk upload of documents to a specific collection asynchronously.
    Documents will be processed in a background task.

    Args:
        db (Session): Database session dependency.
        collection_id (str): The ID of the collection to upload documents to.
        background_tasks (BackgroundTasks): FastAPI's dependency for running background tasks.
        files (List[UploadFile]): The list of uploaded files.
        document_service (DocumentService): Dependency for document-related operations.
        collection_service (CollectionService): Dependency for collection-related operations.
        storage_service (StorageService): Dependency for storage-related operations.

    Returns:
        List[DocumentInDB]: A list of the newly created document details.
    """
    logger.debug(f"API: Received upload request for {len(files)} files to collection {collection_id}.")
    
    pending_docs = document_service.create_documents_from_upload(
        db=db,
        files=files,
        collection_id=collection_id,
        storage_service=storage_service,
        collection_service=collection_service
    )
    logger.debug(f"API: Created {len(pending_docs)} pending documents for collection {collection_id}. IDs: {[doc.id for doc in pending_docs]}")
    
    response_docs = []
    for doc in pending_docs:
        response_outline_pydantic = []
        if hasattr(doc, '_outline_data_for_pydantic') and doc._outline_data_for_pydantic:
            response_outline_pydantic = [
                DocumentOutlineItemPydantic.model_validate(item)
                for item in doc._outline_data_for_pydantic
            ]
        elif hasattr(doc, 'outline_items') and doc.outline_items:
            response_outline_pydantic = [
                DocumentOutlineItemPydantic.model_validate(item, from_attributes=True)
                for item in doc.outline_items
            ]

        response_docs.append(
            DocumentInDB(
                docTitle=doc.docTitle,
                id=doc.id,
                collectionId=doc.collectionId,
                docName=doc.docName,
                docSizeKB=doc.docSizeKB,
                total_pages=doc.total_pages,
                docType=doc.docType,
                docUrl=doc.docUrl,
                createdAt=doc.createdAt,
                updatedAt=doc.updatedAt,
                latestInsightId=doc.latestInsightId,
                latestPodcastId=doc.latestPodcastId,
                isProcessed=ProcessingStatus.SUCCESS,
                isEmbeddingCreated=ProcessingStatus.PENDING,
                outline=response_outline_pydantic
            )
        )
    from app.services.recommender_service import get_recommender_service
    recommender_service = get_recommender_service()
    background_tasks.add_task(
        recommender_service.update_embeddings_for_collection,
        db,
        storage_service,
        collection_id
    )
    logger.debug(f"API: Responding to collection-specific document upload with {len(response_docs)} documents.")
    return response_docs

@router.get(
    "/collections/{collection_id}/documents",
    response_model=List[DocumentInDB],
    summary="Retrieve all documents in a collection",
    description="Fetches a list of all documents belonging to a specific collection, identified by its ID. Returns an empty list if the collection has no documents."
)
def read_documents_in_collection(
    *,
    db: Session = Depends(get_db),
    collection_id: str, # Removed Field(...)
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Retrieve all documents within a specific collection.

    Args:
        db (Session): Database session dependency.
        collection_id (str): The ID of the collection to retrieve documents from.
        document_service (DocumentService): Dependency for document-related operations.

    Returns:
        List[DocumentInDB]: A list of documents within the specified collection.
    """
    logger.debug(f"API: Retrieving documents for collection {collection_id}.")
    db_docs = document_service.get_documents_by_collection(db=db, collection_id=collection_id)
    logger.debug(f"API: Retrieved {len(db_docs)} documents for collection {collection_id}.")
    return [DocumentInDB.model_validate(doc, from_attributes=True) for doc in db_docs]

@router.get(
    "/{document_id}",
    response_model=DocumentInDB,
    summary="Retrieve a single document by ID",
    description="Fetches a single document's details using its unique identifier. Returns a 404 error if the document is not found."
)
def read_document(
    *,
    db: Session = Depends(get_db),
    document_id: str, # Removed Field(...)
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Retrieve a single document by its ID.

    Args:
        db (Session): Database session dependency.
        document_id (str): The ID of the document to retrieve.
        document_service (DocumentService): Dependency for document-related operations.

    Raises:
        HTTPException: 404 Not Found if the document does not exist.

    Returns:
        DocumentInDB: The requested document's details.
    """
    logger.debug(f"API: Received request to read document: {document_id}")
    db_doc = document_service.get_document(db=db, document_id=document_id)
    if db_doc is None:
        logger.warning(f"API: Document {document_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    logger.debug(f"API: Retrieved document {document_id}. isProcessed: {db_doc.isProcessed}, Outline items count: {len(db_doc.outline_items) if hasattr(db_doc, 'outline_items') else 'N/A'}")
    
    response_outline_pydantic = []
    if hasattr(db_doc, '_outline_data_for_pydantic') and db_doc._outline_data_for_pydantic:
        response_outline_pydantic = [
            DocumentOutlineItemPydantic.model_validate(item)
            for item in db_doc._outline_data_for_pydantic
        ]
    elif hasattr(db_doc, 'outline_items') and db_doc.outline_items:
        response_outline_pydantic = [
            DocumentOutlineItemPydantic.model_validate(item, from_attributes=True)
            for item in db_doc.outline_items
        ]

    response_model = DocumentInDB(
        docTitle=db_doc.docTitle,
        id=db_doc.id,
        collectionId=db_doc.collectionId,
        docName=db_doc.docName,
        docSizeKB=db_doc.docSizeKB,
        total_pages=db_doc.total_pages,
        docType=db_doc.docType,
        docUrl=db_doc.docUrl,
        createdAt=db_doc.createdAt,
        updatedAt=db_doc.updatedAt,
        latestInsightId=db_doc.latestInsightId,
        latestPodcastId=db_doc.latestPodcastId,
        isProcessed=ProcessingStatus(db_doc.isProcessed),
        outline=response_outline_pydantic
    )
    logger.debug(f"API: Successfully returned document {document_id}.")
    return response_model

@router.delete(
    "/{document_id}",
    response_model=DocumentInDB,
    summary="Delete a document",
    description="Deletes a document using its unique identifier. This action also triggers a background task to refresh the embeddings for the associated collection. Returns a 404 error if the document is not found."
)
def delete_document(
    *,
    db: Session = Depends(get_db),
    document_id: str, # Removed Field(...)
    document_service: DocumentService = Depends(get_document_service),
    storage_service: StorageService = Depends(get_storage_service),
    background_tasks: BackgroundTasks
):
    """
    Delete a document. This will also trigger a background task to
    refresh the embeddings for the collection.

    Args:
        db (Session): Database session dependency.
        document_id (str): The ID of the document to delete.
        document_service (DocumentService): Dependency for document-related operations.
        background_tasks (BackgroundTasks): FastAPI's dependency for running background tasks.

    Raises:
        HTTPException: 404 Not Found if the document does not exist.

    Returns:
        DocumentInDB: The details of the deleted document.
    """
    logger.debug(f"[DELETE] API: Starting deletion for document ID: {document_id}")
    db_doc = document_service.get_document(db=db, document_id=document_id)
    if db_doc is None:
        logger.warning(f"[DELETE FAILURE] API: Document {document_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    collection_id_to_update = db_doc.collectionId
    logger.debug(f"[DELETE] API: Document {document_id} belongs to collection {collection_id_to_update}")

    response_model = DocumentInDB.model_validate(db_doc, from_attributes=True)
    deleted_doc = document_service.delete_document(db=db, document_id=document_id)
    if deleted_doc is None:
        logger.error(f"[DELETE FAILURE] API: Document {document_id} deletion failed after retrieval")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Schedule the embedding update for the associated collection as a background task
    if collection_id_to_update:
        from app.services.recommender_service import get_recommender_service
        recommender_service = get_recommender_service()
        background_tasks.add_task(
            recommender_service.update_embeddings_for_collection,
            db,
            storage_service,  # Use the injected storage_service
            collection_id_to_update
        )
        logger.debug(f"API: Scheduled embedding update for collection {collection_id_to_update} after document deletion.")

    logger.info(
        f"[DELETE SUCCESS] API: Deleted document {document_id} from collection {collection_id_to_update}. "
        f"Title: {response_model.docTitle}, Type: {response_model.docType}"
    )
    return response_model
