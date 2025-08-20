import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import services, models, and dependencies
from app.services.collection_service import get_collection_service, CollectionService
from app.schemas.collection import CollectionCreate, CollectionUpdate, CollectionInDB # Import Pydantic models
from app.db.session import get_db

# Configure logger for this module
logger = logging.getLogger(__name__)

# Create a new router for this module.
# All routes defined here will be prefixed with what's defined in main.py.
router = APIRouter()

@router.post(
    "/",
    response_model=CollectionInDB,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new collection",
    description="Creates a new collection with the provided name, description, and tags. The collection's ID, creation timestamp, and document count are returned upon successful creation."
)
def create_collection(
    *,
    db: Session = Depends(get_db),
    collection_in: CollectionCreate,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """
    Create a new collection.

    Args:
        db (Session): Database session dependency.
        collection_in (CollectionCreate): The collection data to create.
        collection_service (CollectionService): Dependency for collection-related operations.

    Returns:
        CollectionInDB: The newly created collection's details.
    """
    logger.debug(f"Attempting to create collection with name: {collection_in.name}")
    db_collection = collection_service.create_collection(db=db, collection_in=collection_in)
    
    # Since total_docs is a dynamic field not in the DB, we construct the
    # response model and set it manually.
    response_model = CollectionInDB.model_validate(db_collection, from_attributes=True)
    response_model.total_docs = len(db_collection.documents)
    response_model.latestInsightId = db_collection.latestInsightId
    response_model.latestPodcastId = db_collection.latestPodcastId
    logger.debug(f"Successfully created collection with ID: {response_model.id}")
    return response_model

@router.get(
    "/",
    response_model=List[CollectionInDB],
    summary="Retrieve all collections",
    description="Fetches a list of all collections available in the database, including their associated metadata and document counts."
)
def read_collections(
    db: Session = Depends(get_db),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """
    Retrieve all collections.

    Args:
        db (Session): Database session dependency.
        collection_service (CollectionService): Dependency for collection-related operations.

    Returns:
        List[CollectionInDB]: A list of all collections.
    """
    logger.debug("Attempting to retrieve all collections.")
    db_collections = collection_service.get_all_collections(db=db)
    
    # Manually calculate total_docs for each collection in the list.
    response_list = []
    for collection in db_collections:
        response_model = CollectionInDB.model_validate(collection, from_attributes=True)
        response_model.total_docs = len(collection.documents)
        response_model.latestInsightId = collection.latestInsightId
        response_model.latestPodcastId = collection.latestPodcastId
        response_list.append(response_model)
    logger.debug(f"Successfully retrieved {len(response_list)} collections.")
    return response_list

@router.get(
    "/{collection_id}",
    response_model=CollectionInDB,
    summary="Retrieve a single collection by ID",
    description="Fetches a single collection's details using its unique identifier. Returns a 404 error if the collection is not found."
)
def read_collection(
    *,
    db: Session = Depends(get_db),
    collection_id: str,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """
    Retrieve a single collection by its ID.

    Args:
        db (Session): Database session dependency.
        collection_id (str): The unique identifier of the collection to retrieve.
        collection_service (CollectionService): Dependency for collection-related operations.

    Raises:
        HTTPException: 404 Not Found if the collection does not exist.

    Returns:
        CollectionInDB: The requested collection's details.
    """
    logger.debug(f"Attempting to retrieve collection with ID: {collection_id}")
    db_collection = collection_service.get_collection(db=db, collection_id=collection_id)
    if db_collection is None:
        logger.warning(f"Collection with ID: {collection_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        
    response_model = CollectionInDB.model_validate(db_collection, from_attributes=True)
    response_model.total_docs = len(db_collection.documents)
    response_model.latestInsightId = db_collection.latestInsightId
    response_model.latestPodcastId = db_collection.latestPodcastId
    logger.debug(f"Successfully retrieved collection with ID: {collection_id}")
    return response_model

@router.patch(
    "/{collection_id}",
    response_model=CollectionInDB,
    summary="Update an existing collection",
    description="Updates an existing collection's details using its unique identifier. Allows for partial updates (e.g., changing only the name or description). Returns a 404 error if the collection is not found."
)
def update_collection(
    *,
    db: Session = Depends(get_db),
    collection_id: str,
    collection_in: CollectionUpdate,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """
    Update an existing collection. Allows for partial updates.

    Args:
        db (Session): Database session dependency.
        collection_id (str): The unique identifier of the collection to update.
        collection_in (CollectionUpdate): The updated collection data.
        collection_service (CollectionService): Dependency for collection-related operations.

    Raises:
        HTTPException: 404 Not Found if the collection does not exist.

    Returns:
        CollectionInDB: The updated collection's details.
    """
    logger.debug(f"Attempting to update collection with ID: {collection_id} with data: {collection_in.model_dump_json()}")
    db_collection = collection_service.update_collection(db=db, collection_id=collection_id, collection_in=collection_in)
    if db_collection is None:
        logger.warning(f"Collection with ID: {collection_id} not found for update.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        
    response_model = CollectionInDB.model_validate(db_collection, from_attributes=True)
    response_model.total_docs = len(db_collection.documents)
    response_model.latestInsightId = db_collection.latestInsightId
    response_model.latestPodcastId = db_collection.latestPodcastId
    logger.debug(f"Successfully updated collection with ID: {collection_id}")
    return response_model

@router.delete(
    "/{collection_id}",
    response_model=CollectionInDB,
    summary="Delete a collection",
    description="Deletes a collection and all of its associated documents using its unique identifier. Returns a 404 error if the collection is not found."
)
def delete_collection(
    *,
    db: Session = Depends(get_db),
    collection_id: str,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """
    Delete a collection and all of its associated documents.

    Args:
        db (Session): Database session dependency.
        collection_id (str): The unique identifier of the collection to delete.
        collection_service (CollectionService): Dependency for collection-related operations.

    Raises:
        HTTPException: 404 Not Found if the collection does not exist.

    Returns:
        CollectionInDB: The details of the deleted collection.
    """
    logger.debug(f"[DELETE] Starting deletion for collection ID: {collection_id}")
    # We need to get the doc count before deleting
    db_collection = collection_service.get_collection(db=db, collection_id=collection_id)
    if db_collection is None:
        logger.warning(f"Collection with ID: {collection_id} not found for deletion.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    
    # Create the response model before the object is deleted from the session
    response_model = CollectionInDB.model_validate(db_collection, from_attributes=True)
    response_model.total_docs = len(db_collection.documents)
    response_model.latestInsightId = db_collection.latestInsightId
    response_model.latestPodcastId = db_collection.latestPodcastId

    deleted_collection = collection_service.delete_collection(db=db, collection_id=collection_id)
    if deleted_collection is None:
        logger.error(f"[DELETE FAILURE] Collection {collection_id} deletion failed after retrieval")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    
    logger.info(
        f"[DELETE SUCCESS] Collection {collection_id} deleted. "
        f"Documents removed: {response_model.total_docs}, "
        f"Insight ID: {response_model.latestInsightId}, "
        f"Podcast ID: {response_model.latestPodcastId}"
    )
    return response_model
