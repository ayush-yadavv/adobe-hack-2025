import uuid
import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func # Import func here
from app.services.storage_service import get_storage_service

from app.models.collection import Collection as CollectionModel # Import SQLAlchemy Collection model
from app.schemas.collection import CollectionCreate, CollectionUpdate, CollectionInDB # Import Pydantic models

# Configure logger for this module
logger = logging.getLogger(__name__)

class CollectionService:
    """
    A service class containing the business logic for collection operations.
    """

    def create_collection(self, db: Session, collection_in: CollectionCreate) -> CollectionModel:
        """
        Creates a new collection in the database.

        Args:
            db: The SQLAlchemy database session.
            collection_in: The Pydantic model containing the data for the new collection.

        Returns:
            The newly created SQLAlchemy Collection object.
        """
        logger.debug(f"CollectionService: Attempting to create collection with name: {collection_in.name}")
        # Generate a unique ID for the collection
        collection_id = f"collection_{uuid.uuid4().hex}"
        
        # Create a new SQLAlchemy Collection instance from the Pydantic model
        db_collection = CollectionModel(
            id=collection_id,
            name=collection_in.name,
            description=collection_in.description,
            tags=json.dumps(collection_in.tags) if collection_in.tags else None,
            createdAt=func.now(), # Explicitly set createdAt
            updatedAt=func.now()  # Explicitly set updatedAt
        )
        
        db.add(db_collection)
        db.commit()
        db.refresh(db_collection)
        logger.debug(f"CollectionService: Successfully created collection with ID: {db_collection.id}")
        return db_collection

    def get_collection(self, db: Session, collection_id: str) -> Optional[CollectionModel]:
        """
        Retrieves a single collection by its ID.

        Args:
            db: The SQLAlchemy database session.
            collection_id: The ID of the collection to retrieve.

        Returns:
            The SQLAlchemy Collection object if found, otherwise None.
        """
        logger.debug(f"CollectionService: Attempting to retrieve collection with ID: {collection_id}")
        collection = db.query(CollectionModel).filter(CollectionModel.id == collection_id).first()
        if collection:
            logger.debug(f"CollectionService: Found collection with ID: {collection_id}")
        else:
            logger.debug(f"CollectionService: Collection with ID: {collection_id} not found.")
        return collection

    def get_all_collections(self, db: Session) -> List[CollectionModel]:
        """
        Retrieves all collections from the database.

        Args:
            db: The SQLAlchemy database session.

        Returns:
            A list of all SQLAlchemy Collection objects.
        """
        logger.debug("CollectionService: Attempting to retrieve all collections.")
        collections = db.query(CollectionModel).all()
        logger.debug(f"CollectionService: Retrieved {len(collections)} collections.")
        return collections

    def update_collection(self, db: Session, collection_id: str, collection_in: CollectionUpdate) -> Optional[CollectionModel]:
        """
        Updates an existing collection.

        Args:
            db: The SQLAlchemy database session.
            collection_id: The ID of the collection to update.
            collection_in: A Pydantic model with the fields to update.

        Returns:
            The updated SQLAlchemy Collection object if found, otherwise None.
        """
        logger.debug(f"CollectionService: Attempting to update collection with ID: {collection_id}")
        db_collection = self.get_collection(db, collection_id)
        if not db_collection:
            logger.debug(f"CollectionService: Collection with ID: {collection_id} not found for update.")
            return None
            
        update_data = collection_in.model_dump(exclude_unset=True)
        
        # Handle tags update correctly
        if 'tags' in update_data and update_data['tags'] is not None:
            update_data['tags'] = json.dumps(update_data['tags'])

        for key, value in update_data.items():
            setattr(db_collection, key, value)
            
        db.add(db_collection)
        db.commit()
        db.refresh(db_collection)
        logger.debug(f"CollectionService: Successfully updated collection with ID: {collection_id}")
        return db_collection

    def delete_collection(self, db: Session, collection_id: str) -> Optional[CollectionModel]:
        """
        Deletes a collection and its storage directory from the database.

        Args:
            db: The SQLAlchemy database session.
            collection_id: The ID of the collection to delete.

        Returns:
            The deleted SQLAlchemy Collection object if found, otherwise None.
        """
        logger.debug(f"[DELETE] CollectionService: Starting deletion for collection ID: {collection_id}")
        db_collection = self.get_collection(db, collection_id)
        if not db_collection:
            logger.warning(f"[DELETE FAILURE] CollectionService: Collection {collection_id} not found")
            return None
            
        # Delete all documents in the collection (which deletes their files)
        from app.services.document_service import get_document_service
        document_service = get_document_service()
        for document in db_collection.documents:
            document_service.delete_document(db, document.id)
            
        logger.debug(f"[DELETE] CollectionService: Deleting collection {collection_id} with {len(db_collection.documents)} documents")
        db.delete(db_collection)
        db.commit()
        
        # Delete collection storage directory
        try:
            storage_service = get_storage_service()
            storage_service.delete_collection_directory(collection_id)
            logger.info(f"[DELETE SUCCESS] CollectionService: Deleted collection {collection_id} and its storage")
        except Exception as e:
            logger.error(f"[DELETE WARNING] CollectionService: Failed to delete storage for collection {collection_id}: {str(e)}")
            
        return db_collection

# Create a single instance of the service to be used as a dependency
collection_service = CollectionService()

def get_collection_service():
    """
    Dependency function to provide the collection service instance.
    """
    return collection_service
