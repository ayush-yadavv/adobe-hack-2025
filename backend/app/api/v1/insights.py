import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

# Configure logger for this module
logger = logging.getLogger(__name__)

# Import services, models, and dependencies
from app.services.insights_service import get_insight_service, InsightService
from app.schemas.insight import InsightInDB # Use the updated Pydantic schema
from app.models.insight import Insight as InsightModel # SQLAlchemy model
from app.db.session import get_db

# Create a new router for this module.
router = APIRouter()

@router.get(
    "/generate",
    response_model=InsightInDB,
    status_code=status.HTTP_200_OK,
    summary="Generate and retrieve insights for an entity",
    description="Generates and retrieves structured insights for a specified document, collection, or recommendation. Exactly one of `doc_id`, `col_id`, or `rec_id` must be provided. The generated insight is stored and returned."
)
def generate_insights_for_entity(
    *,
    db: Session = Depends(get_db),
    doc_id: Optional[str] = Query(None, description="ID of the document to generate insights for."),
    col_id: Optional[str] = Query(None, description="ID of the collection to generate insights for."),
    rec_id: Optional[str] = Query(None, description="ID of the recommendation to generate insights for."),
    insight_service: InsightService = Depends(get_insight_service)
):
    """
    Generates and retrieves insights for a specified document, collection, or recommendation.
    Only one of doc_id, col_id, or rec_id should be provided.

    Args:
        db (Session): Database session dependency.
        doc_id (Optional[str]): The ID of the document for which to generate insights.
        col_id (Optional[str]): The ID of the collection for which to generate insights.
        rec_id (Optional[str]): The ID of the recommendation for which to generate insights.
        insight_service (InsightService): Dependency for insight generation operations.

    Raises:
        HTTPException: 400 Bad Request if more or less than one ID is provided.
        HTTPException: 500 Internal Server Error for unexpected errors during generation.

    Returns:
        InsightInDB: The newly generated insight.
    """
    logger.debug(f"API: Received insight generation request. doc_id: {doc_id}, col_id: {col_id}, rec_id: {rec_id}")
    if sum([bool(doc_id), bool(col_id), bool(rec_id)]) != 1:
        logger.warning("API: Exactly one of 'doc_id', 'col_id', or 'rec_id' must be provided for insight generation.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of 'doc_id', 'col_id', or 'rec_id' must be provided."
        )
    
    try:
        new_insight = insight_service.generate_and_store_insight(
            db=db,
            doc_id=doc_id,
            col_id=col_id,
            rec_id=rec_id
        )
        logger.debug(f"API: Successfully generated insight with ID: {new_insight.insightId}")
        return new_insight
    except HTTPException as e:
        logger.error(f"API: HTTP Exception during insight generation: {e.detail}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"API: An unexpected error occurred during insight generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during insight generation: {e}"
        )

@router.get(
    "/{insight_id}",
    response_model=InsightInDB,
    summary="Retrieve a single insight by ID",
    description="Fetches a single insight's details using its unique identifier. Returns a 404 error if the insight is not found."
)
def get_insight_by_id(
    *,
    db: Session = Depends(get_db),
    insight_id: str = Path(..., description="The unique identifier of the insight to retrieve.") # Changed to Path
):
    """
    Retrieve a single insight by its ID.

    Args:
        db (Session): Database session dependency.
        insight_id (str): The ID of the insight to retrieve.

    Raises:
        HTTPException: 404 Not Found if the insight does not exist.

    Returns:
        InsightInDB: The requested insight's details.
    """
    logger.debug(f"API: Attempting to retrieve insight with ID: {insight_id}")
    insight = db.query(InsightModel).filter(InsightModel.insightId == insight_id).first()
    if not insight:
        logger.warning(f"API: Insight with ID: {insight_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found"
        )
    logger.debug(f"API: Successfully retrieved insight with ID: {insight_id}")
    return insight
