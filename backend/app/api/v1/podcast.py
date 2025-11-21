import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session

# Configure logger for this module
logger = logging.getLogger(__name__)

# Import services, models, and dependencies
from app.services.podcast_service import get_podcast_service, PodcastService
from app.services.storage_service import get_storage_service, StorageService
from app.schemas.podcast import PodcastGenerateRequest, PodcastInDB 
from app.models.podcast import Podcast 
from app.db.session import get_db

# Create a new router for this module.
router = APIRouter()

@router.post(
    "/generate/from-document/{document_id}",
    response_model=PodcastInDB,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a podcast from a document",
    description="Generates an audio podcast from the content of a specified document. The generation process is synchronous. Returns the details of the newly created podcast, including its audio URL and transcript."
)
def generate_podcast_from_document(
    *,
    db: Session = Depends(get_db),
    document_id: str = Path(..., description="The ID of the document to generate the podcast from."),
    podcast_in: PodcastGenerateRequest,
    podcast_service: PodcastService = Depends(get_podcast_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    """
    Synchronously generate a podcast from a single document.

    Args:
        db (Session): Database session dependency.
        document_id (str): The ID of the document to generate the podcast from.
        podcast_in (PodcastGenerateRequest): Request body containing podcast generation options.
        podcast_service (PodcastService): Dependency for podcast generation operations.
        storage_service (StorageService): Dependency for storage operations.

    Returns:
        PodcastInDB: The newly created podcast's details.

    Raises:
        HTTPException: 500 Internal Server Error for unexpected errors during generation.
    """
    logger.info(f"API: Received request to generate podcast from document ID: {document_id}")
    try:
        db_podcast = podcast_service.generate_podcast_for_document(
            db=db,
            storage_service=storage_service,
            document_id=document_id,
            podcast_in=podcast_in,
            include_insights=podcast_in.include_insights
        )
        logger.info(f"API: Successfully generated podcast {db_podcast.podcastId} from document {document_id}.")
        return db_podcast
    except HTTPException as e:
        logger.error(f"API: HTTP Exception during document podcast generation for {document_id}: {e.detail}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"API: An unexpected error occurred during document podcast generation for {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while generating the podcast: {str(e)}"
        )

@router.post(
    "/generate/from-recommendation/{recommendation_id}",
    response_model=dict,  # Changed to dict to include additional metadata
    status_code=status.HTTP_201_CREATED,
    summary="Generate a podcast from a recommendation",
    description="Generates an audio podcast from the content of a specified recommendation. The generation process is synchronous. Returns the details of the newly created podcast, including its audio URL and transcript, plus confirmation that the recommendation's latestPodcastId was updated."
)
def generate_podcast_from_recommendation(
    *,
    db: Session = Depends(get_db),
    recommendation_id: str = Path(..., description="The ID of the recommendation to generate the podcast from."),
    podcast_in: PodcastGenerateRequest,
    podcast_service: PodcastService = Depends(get_podcast_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    """
    Synchronously generate a podcast from a specific recommendation event.

    Args:
        db (Session): Database session dependency.
        recommendation_id (str): The ID of the recommendation to generate the podcast from.
        podcast_in (PodcastGenerateRequest): Request body containing podcast generation options.
        podcast_service (PodcastService): Dependency for podcast generation operations.
        storage_service (StorageService): Dependency for storage operations.

    Returns:
        dict: The newly created podcast's details plus metadata about the updated recommendation.

    Raises:
        HTTPException: 500 Internal Server Error for unexpected errors during generation.
    """
    from app.models.recommendation import Recommendation
    
    logger.info(f"API: Received request to generate podcast from recommendation ID: {recommendation_id}")
    try:
        db_podcast = podcast_service.generate_podcast_for_recommendation(
            db=db,
            storage_service=storage_service,
            recommendation_id=recommendation_id,
            podcast_in=podcast_in,
            include_insights=podcast_in.include_insights
        )
        
        # Fetch the updated recommendation to confirm latestPodcastId was set
        db_recommendation = db.query(Recommendation).filter(
            Recommendation.recommendation_id == recommendation_id
        ).first()
        
        # Convert podcast to dict and add metadata
        podcast_dict = PodcastInDB.model_validate(db_podcast, from_attributes=True).model_dump()
        podcast_dict["_metadata"] = {
            "recommendation_latest_podcast_id": db_recommendation.latest_podcast_id if db_recommendation else None,
            "recommendation_updated": db_recommendation.latest_podcast_id == db_podcast.podcastId if db_recommendation else False
        }
        
        logger.info(f"API: Successfully generated podcast {db_podcast.podcastId} from recommendation {recommendation_id}. Recommendation latestPodcastId: {db_recommendation.latest_podcast_id if db_recommendation else 'N/A'}")
        return podcast_dict
    except HTTPException as e:
        logger.error(f"API: HTTP Exception during recommendation podcast generation for {recommendation_id}: {e.detail}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"API: An unexpected error occurred during recommendation podcast generation for {recommendation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while generating the podcast: {str(e)}"
        )

@router.get(
    "/{podcast_id}",
    response_model=PodcastInDB,
    summary="Retrieve a single podcast by ID",
    description="Fetches a single podcast's details using its unique identifier. Returns a 404 error if the podcast is not found."
)
def get_podcast(
    *,
    db: Session = Depends(get_db),
    podcast_id: str = Path(..., description="The unique identifier of the podcast to retrieve.")
):
    """
    Retrieve a single podcast by its ID.

    Args:
        db (Session): Database session dependency.
        podcast_id (str): The ID of the podcast to retrieve.

    Returns:
        PodcastInDB: The requested podcast's details.

    Raises:
        HTTPException: 404 Not Found if the podcast does not exist.
    """
    logger.debug(f"API: Attempting to retrieve podcast with ID: {podcast_id}")
    podcast = db.query(Podcast).filter(Podcast.podcastId == podcast_id).first()
    if not podcast:
        logger.warning(f"API: Podcast with ID: {podcast_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast not found"
        )
    logger.debug(f"API: Successfully retrieved podcast with ID: {podcast_id}")
    return podcast

@router.post(
    "/generate/from-collection/{collection_id}",
    response_model=dict,  # Changed to dict to include additional metadata
    status_code=status.HTTP_201_CREATED,
    summary="Generate a podcast from a collection",
    description="Generates an audio podcast from the aggregated content of documents within a specified collection. The generation process is synchronous. Returns the details of the newly created podcast, including its audio URL and transcript, plus confirmation that the collection's latestPodcastId was updated."
)
def generate_podcast_from_collection(
    *,
    db: Session = Depends(get_db),
    collection_id: str = Path(..., description="The ID of the collection to generate the podcast from."),
    podcast_in: PodcastGenerateRequest,
    podcast_service: PodcastService = Depends(get_podcast_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    """
    Synchronously generate a podcast from a collection.

    Args:
        db (Session): Database session dependency.
        collection_id (str): The ID of the collection to generate the podcast from.
        podcast_in (PodcastGenerateRequest): Request body containing podcast generation options.
        podcast_service (PodcastService): Dependency for podcast generation operations.
        storage_service (StorageService): Dependency for storage operations.

    Returns:
        dict: The newly created podcast's details plus metadata about the updated collection.

    Raises:
        HTTPException: 500 Internal Server Error for unexpected errors during generation.
    """
    from app.models.collection import Collection
    
    logger.info(f"API: Received request to generate podcast from collection ID: {collection_id}")
    try:
        db_podcast = podcast_service.generate_podcast_for_collection(
            db=db,
            storage_service=storage_service,
            collection_id=collection_id,
            podcast_in=podcast_in,
            include_insights=podcast_in.include_insights
        )
        
        # Fetch the updated collection to confirm latestPodcastId was set
        db_collection = db.query(Collection).filter(
            Collection.id == collection_id
        ).first()
        
        # Convert podcast to dict and add metadata
        podcast_dict = PodcastInDB.model_validate(db_podcast, from_attributes=True).model_dump()
        podcast_dict["_metadata"] = {
            "collection_latest_podcast_id": db_collection.latestPodcastId if db_collection else None,
            "collection_updated": db_collection.latestPodcastId == db_podcast.podcastId if db_collection else False
        }
        
        logger.info(f"API: Successfully generated podcast {db_podcast.podcastId} from collection {collection_id}. Collection latestPodcastId: {db_collection.latestPodcastId if db_collection else 'N/A'}")
        return podcast_dict
    except HTTPException as e:
        logger.error(f"API: HTTP Exception during collection podcast generation for {collection_id}: {e.detail}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"API: An unexpected error occurred during collection podcast generation for {collection_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while generating the podcast: {str(e)}"
        )
