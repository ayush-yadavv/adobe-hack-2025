import uuid
import json
import logging # Import logging
import redis
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.schemas.insight import InsightInDB, InsightItem
from app.models.insight import Insight as InsightModel # SQLAlchemy model
from app.models.document import Document # SQLAlchemy Document model
from app.models.collection import Collection # SQLAlchemy Collection model
from app.models.recommendation import Recommendation # SQLAlchemy Recommendation model

from app.core.insights import LLMManager, ProviderError # Use LLMManager for consistency

# Configure logger for this module
logger = logging.getLogger(__name__)

class InsightService:
    """
    A service class for handling insight generation logic.

    This service orchestrates the generation of structured insights from various
    data sources (documents, collections, recommendations) using an LLM,
    stores them in the database, and manages their lifecycle.
    """
    def __init__(self):
        self.llm_manager: Optional[LLMManager] = None
        try:
            self.llm_manager = LLMManager.from_env()
            logger.info("InsightService: LLMManager initialized successfully.")
        except Exception as e:
            logger.critical(f"InsightService: LLM Manager failed to initialize: {e}", exc_info=True)
            # It's important to raise or handle this, as insight generation won't work without LLM
            # For now, we'll let it proceed with self.llm_manager being None, and handle it in generate_and_store_insight
            

    def _extract_json_from_markdown(self, text: str) -> str:
        """
        Extracts JSON string from a markdown code block.
        Assumes the JSON is within a ```json ... ``` block.

        Args:
            text (str): The input string, potentially containing a markdown JSON block.

        Returns:
            str: The extracted JSON string, or the original text if no markdown block is found.
        """
        logger.debug("InsightService: Attempting to extract JSON from markdown.")
        if text.strip().startswith("```json") and text.strip().endswith("```"):
            extracted_json = text.strip()[len("```json"): -len("```")].strip()
            logger.debug("InsightService: Successfully extracted JSON from markdown.")
            return extracted_json
        logger.debug("InsightService: No JSON markdown block found, returning original text.")
        return text

    def generate_and_store_insight(
        self, 
        db: Session, 
        doc_id: Optional[str] = None, 
        col_id: Optional[str] = None, 
        rec_id: Optional[str] = None
    ) -> InsightInDB:
        """
        Generates insights for a given document, collection, or recommendation,
        stores them, updates the parent entity's latestInsightId, and deletes old insights.

        Args:
            db (Session): The SQLAlchemy database session.
            doc_id (Optional[str]): The ID of the document to generate insights for.
            col_id (Optional[str]): The ID of the collection to generate insights for.
            rec_id (Optional[str]): The ID of the recommendation to generate insights for.

        Returns:
            InsightInDB: The newly created insight object.

        Raises:
            HTTPException: 400 Bad Request if no source ID is provided or no content is found.
            HTTPException: 404 Not Found if the specified source entity does not exist.
            HTTPException: 503 Service Unavailable if the LLM service is not initialized.
            HTTPException: 500 Internal Server Error if LLM generation or parsing fails.
        """
        logger.info(f"InsightService: Starting insight generation for doc_id={doc_id}, col_id={col_id}, rec_id={rec_id}")
        source_id: str
        source_type: str
        context_text: str = ""
        parent_entity: Any = None

        if doc_id:
            source_type = "document"
            source_id = doc_id
            from app.services.document_service import get_document_service
            document_service = get_document_service()
            db_doc = document_service.get_document(db, doc_id)
            if not db_doc:
                logger.warning(f"InsightService: Document with ID {doc_id} not found for insight generation.")
                raise HTTPException(status_code=404, detail=f"Document with ID {doc_id} not found.")
            parent_entity = db_doc
            context_text = " ".join([item.section_text for item in db_doc.outline_items if item.section_text])
            if not context_text:
                logger.warning(f"InsightService: No extractable content found for document {doc_id} for insights.")
                raise HTTPException(status_code=400, detail=f"No content found for document {doc_id} to generate insights.")
            logger.debug(f"InsightService: Generating insights for document {doc_id}. Content length: {len(context_text)}")

        elif col_id:
            source_id = col_id
            source_type = "collection"
            from app.services.collection_service import get_collection_service
            from app.services.document_service import get_document_service
            collection_service = get_collection_service()
            document_service = get_document_service()
            db_collection = collection_service.get_collection(db, col_id)
            if not db_collection:
                logger.warning(f"InsightService: Collection with ID {col_id} not found for insight generation.")
                raise HTTPException(status_code=404, detail=f"Collection with ID {col_id} not found.")
            parent_entity = db_collection
            
            db_docs = document_service.get_documents_by_collection(db, col_id)
            if not db_docs:
                logger.warning(f"InsightService: No documents found in collection {col_id} to generate insights.")
                raise HTTPException(status_code=400, detail=f"No documents found in collection {col_id} to generate insights.")
            
            all_doc_texts = []
            for doc in db_docs:
                doc_content = " ".join([item.section_text for item in doc.outline_items if item.section_text])
                if doc_content:
                    all_doc_texts.append(f"Document: {doc.docTitle or doc.docName}\nContent: {doc_content}")
            context_text = "\n\n".join(all_doc_texts)
            if not context_text:
                logger.warning(f"InsightService: No content found in documents of collection {col_id} to generate insights.")
                raise HTTPException(status_code=400, detail=f"No content found in documents of collection {col_id} to generate insights.")
            logger.debug(f"InsightService: Generating insights for collection {col_id}. Content length: {len(context_text)}")

        elif rec_id:
            source_id = rec_id
            source_type = "recommendation"
            from app.services.recommender_service import get_recommender_service
            recommender_service = get_recommender_service()
            db_recommendation = recommender_service.get_recommendation_by_id(db, rec_id)
            if not db_recommendation:
                logger.warning(f"InsightService: Recommendation with ID {rec_id} not found for insight generation.")
                raise HTTPException(status_code=404, detail=f"Recommendation with ID {rec_id} not found.")
            parent_entity = db_recommendation
            
            if not db_recommendation.items:
                logger.warning(f"InsightService: No items found in recommendation {rec_id} to generate insights.")
                raise HTTPException(status_code=400, detail=f"No items found in recommendation {rec_id} to generate insights.")
            
            all_snippet_texts = []
            for item in db_recommendation.items:
                if item.snippet_text:
                    all_snippet_texts.append(f"Snippet from '{item.document_title}': {item.snippet_text}")
            context_text = "\n\n".join(all_snippet_texts)
            if not context_text:
                logger.warning(f"InsightService: No snippet content found in recommendation {rec_id} to generate insights.")
                raise HTTPException(status_code=400, detail=f"No snippet content found in recommendation {rec_id} to generate insights.")
            logger.debug(f"InsightService: Generating insights for recommendation {rec_id}. Content length: {len(context_text)}")

        else:
            logger.error("InsightService: No source ID (doc_id, col_id, or rec_id) provided.")
            raise HTTPException(status_code=400, detail="One of doc_id, col_id, or rec_id must be provided.")

        if not self.llm_manager:
            logger.critical("InsightService: LLM service is not available. Cannot generate insights.")
            raise HTTPException(status_code=503, detail="LLM service is not available.")

        prompt_messages = [
            {"role": "system", "content": """You are an expert analyst. Based on the provided text, generate a JSON array of high-level insights. Each insight object in the array must have a 'type', 'data', and 'priority' field.
The 'type' field must be one of the following exact values:
- "Key insights"
- "Did you know?"
- "Contradictions / counterpoints"
- "Inspirations or connections across docs"

The 'data' field should contain the actual insight text, limited to a maximum of two concise sentences.
The 'priority' field should be an integer, where lower numbers indicate higher priority (e.g., 1 for most important).

Generate at least one insight. For each of the four types, if applicable, provide one entry. If a type is not applicable, you can omit it. Ensure the output is a valid JSON array.
"""},
            {"role": "user", "content": f"Here is the text:\n\n---\n\n{context_text[:16000]}\n\n---\n\nGenerate insights based on this text."}
        ]

        logger.debug(f"InsightService: Calling LLM for insight generation for {source_type} {source_id}.")
        try:
            llm_insights_response_str = self.llm_manager.get_response(prompt_messages)
            logger.debug(f"InsightService: LLM response for insights (first 200 chars): {llm_insights_response_str[:200]}...")
        except ProviderError as e:
            logger.error(f"InsightService: LLM failed to generate insights for {source_type} {source_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"LLM failed to generate insights: {e}")

        try:
            processed_llm_insights_response_str = self._extract_json_from_markdown(llm_insights_response_str)
            llm_insights_json = json.loads(processed_llm_insights_response_str)
            
            if not isinstance(llm_insights_json, list):
                raise ValueError("LLM response was not a JSON list.")
            
            parsed_insights_data: List[InsightItem] = []
            seen_types = set()
            for item in llm_insights_json:
                try:
                    insight_item = InsightItem(**item)
                    if insight_item.type not in seen_types:
                        sentences = insight_item.data.split('.')
                        truncated_data = ".".join(sentences[:2])
                        if len(sentences) > 2 and truncated_data.strip():
                            truncated_data += "."
                        insight_item.data = truncated_data.strip()
                        
                        parsed_insights_data.append(insight_item)
                        seen_types.add(insight_item.type)
                    else:
                        logger.warning(f"InsightService: Skipping duplicate insight type: {insight_item.type.value}")
                except Exception as item_e:
                    logger.warning(f"InsightService: Skipping malformed insight item: {item}. Error: {item_e}")
            
            if not parsed_insights_data:
                logger.warning("InsightService: LLM generated an empty or invalid list of insights after filtering.")
                raise ValueError("LLM generated an empty or invalid list of insights after filtering.")

        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.error(f"InsightService: Error parsing or validating LLM response for insights: {e}", exc_info=True)
            parsed_insights_data = [InsightItem(type="generation_error", data=f"Failed to parse structured insights or validate. Raw LLM response: {llm_insights_response_str}", priority=1)]

        old_insight_id = getattr(parent_entity, 'latestInsightId', None)
        
        new_insight_id = f"insight_{uuid.uuid4().hex}"
        db_new_insight = InsightModel(
            insightId=new_insight_id,
            sourceId=source_id,
            sourceType=source_type,
            insights_data=json.dumps([item.model_dump() for item in parsed_insights_data])
        )
        db.add(db_new_insight)

        if parent_entity:
            logger.debug(f"InsightService: Before update - {source_type} {source_id} latestInsightId: {getattr(parent_entity, 'latestInsightId', getattr(parent_entity, 'latest_insight_id', 'N/A'))}")
            
            if source_type == "recommendation":
                parent_entity.latest_insight_id = new_insight_id
            else:
                parent_entity.latestInsightId = new_insight_id
            
            logger.debug(f"InsightService: After direct assignment - {source_type} {source_id} latestInsightId (in memory): {getattr(parent_entity, 'latestInsightId', getattr(parent_entity, 'latest_insight_id', 'N/A'))}")
            logger.debug(f"InsightService: Is parent_entity modified before commit? {db.is_modified(parent_entity)}")

            db.merge(parent_entity) 

        db.commit()
        db.refresh(db_new_insight)
        db.refresh(parent_entity)
        logger.info(f"InsightService: New insight {new_insight_id} created and parent updated for {source_type} {source_id}.")

        if old_insight_id:
            logger.info(f"InsightService: Deleting old insight {old_insight_id} for {source_type} {source_id}.")
            db.query(InsightModel).filter(InsightModel.insightId == old_insight_id).delete()
            db.commit()
            logger.info(f"InsightService: Old insight {old_insight_id} deleted.")

        return InsightInDB.model_validate(db_new_insight, from_attributes=True)

# Create a single instance of the service
insight_service = InsightService()

def get_insight_service():
    """
    Dependency function to provide the insight service instance.
    """
    return insight_service

# Explicitly expose the class for direct import
__all__ = ["InsightService", "get_insight_service"]
