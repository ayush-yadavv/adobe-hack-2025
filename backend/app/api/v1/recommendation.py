import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, status, Path

from sqlalchemy.orm import Session

# Import services and models
from app.db.session import get_db
from app.services.recommender_service import RecommenderService, AnalysisRequest, get_recommender_service
from app.services.storage_service import get_storage_service, StorageService

# Import models and schemas
from app.schemas.recommendation import SnippetResponse, Snippet, Insight, SnippetRequest, RecommendationSchema
from app.schemas.recommendation_item import RecommendationItemSchema # Import for explicit typing

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/persona-based",
    response_model=Dict[str, Any], # Changed to Dict[str, Any] as per user feedback
    status_code=status.HTTP_200_OK,
    summary="Generate persona-based recommendations",
    description="Generates a new recommendation based on a specified persona or job-to-be-done. At least one of 'persona' or 'job_to_be_done' must be provided. Returns the newly created recommendation record, including its associated items."
)
def run_analysis(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
    recommender_service: RecommenderService = Depends(get_recommender_service)
) -> Dict[str, Any]: # Changed to Dict[str, Any] as per user feedback
    """
    Generates recommendations based on a persona or job-to-be-done.

    Args:
        request (AnalysisRequest): The request body containing persona or job-to-be-done.
        db (Session): Database session dependency.
        recommender_service (RecommenderService): Dependency for recommender operations.

    Returns:
        Dict[str, Any]: The newly generated recommendation.

    Raises:
        HTTPException: 400 Bad Request if neither persona nor job_to_be_done is provided.
    """
    logger.info(f"API: Received request for persona-based analysis. Persona: '{request.persona}', Job-to-be-done: '{request.job_to_be_done}'")
    if not (request.persona or request.job_to_be_done):
        logger.warning("API: Neither 'persona' nor 'job_to_be_done' provided for persona-based analysis.")
        raise HTTPException(status_code=400, detail="For persona-based analysis, 'persona' or 'job_to_be_done' must be provided.")
    
    result = recommender_service.run_analysis(request, db)
    logger.info(f"API: Successfully generated persona-based recommendation with ID: {result.recommendation_id}")
    return RecommendationSchema.model_validate(result, from_attributes=True).model_dump(exclude_none=False) # Ensure proper Pydantic model validation

@router.post(
    "/text-based",
    response_model=Dict[str, Any], # Changed to Dict[str, Any] as per user feedback
    status_code=status.HTTP_200_OK,
    summary="Generate text-based recommendations",
    description="Generates a new recommendation based on a user's selected text and a list of collection IDs to search within. Returns the newly created recommendation record, including its associated items."
)
def get_text_based_recommendations(
    selected_text: str = Body(..., embed=True, description="The text selected by the user."),
    collection_ids: List[str] = Body(..., embed=True, description="List of collection IDs to search within."),
    db: Session = Depends(get_db),
    recommender_service: RecommenderService = Depends(get_recommender_service),
    storage_service: StorageService = Depends(get_storage_service)
) -> Dict[str, Any]: # Changed to Dict[str, Any] as per user feedback
    """
    Generates recommendations based on a user's text selection.

    Args:
        selected_text (str): The text selected by the user.
        collection_ids (List[str]): A list of collection IDs to search within.
        db (Session): Database session dependency.
        recommender_service (RecommenderService): Dependency for recommender operations.

    Returns:
        Dict[str, Any]: The newly generated recommendation.

    Raises:
        HTTPException: 400 Bad Request if selected text is empty or no collection IDs are provided.
    """
    logger.info(f"API: Received request for text-based recommendations. Selected text: '{selected_text[:50]}...', Collections: {collection_ids}")
    if not selected_text.strip():
        logger.warning("API: Selected text is empty for text-based recommendations.")
        raise HTTPException(status_code=400, detail="Selected text cannot be empty for text-based recommendations.")
    if not collection_ids:
        logger.warning("API: No collection IDs provided for text-based recommendations.")
        raise HTTPException(status_code=400, detail="Collection IDs must be provided for text-based recommendations.")
    
    result = recommender_service.get_selection_recommendations_api(db, storage_service, selected_text, collection_ids)
    logger.info(f"API: Successfully generated text-based recommendation with ID: {result.recommendation_id}")
    return RecommendationSchema.model_validate(result, from_attributes=True).model_dump(exclude_none=False) # Ensure proper Pydantic model validation

@router.get(
    "/collections/{collection_id}",
    response_model=List[Dict[str, Any]], # Changed to List[Dict[str, Any]] as per user feedback
    summary="Retrieve all recommendations for a collection",
    description="Fetches a list of all recommendation records associated with a specific collection. The response includes basic recommendation details but excludes the full content of associated items for brevity."
)
def get_all_recommendations_for_collection(
    *,
    db: Session = Depends(get_db),
    collection_id: str = Path(..., description="The ID of the collection to retrieve recommendations for."),
    recommender_service: RecommenderService = Depends(get_recommender_service)
) -> List[Dict[str, Any]]: # Changed to List[Dict[str, Any]] as per user feedback
    """
    Get all recommendation records for a collection, without their associated items.

    Args:
        db (Session): Database session dependency.
        collection_id (str): The ID of the collection.
        recommender_service (RecommenderService): Dependency for recommender operations.

    Returns:
        List[Dict[str, Any]]: A list of recommendation records for the specified collection.
    """
    logger.debug(f"API: Retrieving all recommendations for collection ID: {collection_id}")
    db_recs = recommender_service.get_recommendations_for_collection(db=db, collection_id=collection_id)
    
    response_recs = []
    for rec in db_recs:
        response_recs.append(
            RecommendationSchema(
                recommendation_id=rec.recommendation_id,
                collection_id=rec.collection_id,
                user_selection_text=rec.user_selection_text,
                latest_podcast_id=rec.latest_podcast_id,
                latest_insight_id=rec.latest_insight_id,
                generated_at=rec.generated_at,
                recommendation_type=rec.recommendation_type,
                items=[] # Explicitly set items to an empty list for this endpoint
            ).model_dump(exclude_none=False) # Force include all fields
        )
    logger.debug(f"API: Retrieved {len(response_recs)} recommendations for collection {collection_id}.")
    return response_recs

@router.get(
    "/{recommendation_id}",
    response_model=Dict[str, Any], # Changed to Dict[str, Any] as per user feedback
    summary="Retrieve a specific recommendation by ID",
    description="Fetches a single recommendation record by its unique ID, including all its associated items (snippets and explanations). Returns a 404 error if the recommendation is not found."
)
def get_recommendation(
    *,
    db: Session = Depends(get_db),
    recommendation_id: str = Path(..., description="The ID of the recommendation to retrieve."),
    recommender_service: RecommenderService = Depends(get_recommender_service)
) -> Dict[str, Any]: # Changed to Dict[str, Any] as per user feedback
    """
    Get a specific recommendation record by its ID, including its items.

    Args:
        db (Session): Database session dependency.
        recommendation_id (str): The ID of the recommendation.
        recommender_service (RecommenderService): Dependency for recommender operations.

    Returns:
        Dict[str, Any]: The requested recommendation, including its items.

    Raises:
        HTTPException: 404 Not Found if the recommendation does not exist.
    """
    logger.debug(f"API: Retrieving recommendation with ID: {recommendation_id}")
    rec = recommender_service.get_recommendation_by_id(db=db, recommendation_id=recommendation_id)
    if not rec:
        logger.warning(f"API: Recommendation with ID: {recommendation_id} not found.")
        raise HTTPException(status_code=404, detail="Recommendation not found")
    logger.debug(f"API: Successfully retrieved recommendation with ID: {recommendation_id}.")
    return RecommendationSchema.model_validate(rec, from_attributes=True).model_dump(exclude_none=False)

@router.delete(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Delete one or more recommendations",
    description="Deletes one or more recommendation records by their IDs. Accepts a list of recommendation IDs in the request body."
)
def delete_recommendations(
    *,
    db: Session = Depends(get_db),
    recommendation_ids: List[str] = Body(..., embed=True, description="List of recommendation IDs to delete."), # Reverted to List[str] in Body
    recommender_service: RecommenderService = Depends(get_recommender_service)
):
    """
    Delete one or more recommendation records by their IDs.

    Args:
        db (Session): Database session dependency.
        recommendation_ids (List[str]): List of recommendation IDs to delete.
        recommender_service (RecommenderService): Dependency for recommender operations.

    Returns:
        Dict[str, str]: A message indicating the number of recommendations deleted.
    """
    logger.info(f"API: Received request to delete recommendations with IDs: {recommendation_ids}")
    num_deleted = recommender_service.delete_recommendations(db=db, recommendation_ids=recommendation_ids)
    logger.info(f"API: Successfully deleted {num_deleted} recommendation(s).")
    return {"message": f"Successfully deleted {num_deleted} recommendation(s)."}
