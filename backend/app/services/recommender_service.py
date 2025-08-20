import uuid
import pickle
import faiss
import json
import logging # Import logging
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.core.config import settings
from app.core.pdf_parser import get_quad_points_for_text
from app.services.storage_service import StorageService
from pydantic import BaseModel

# Import schemas and models from the original project structure
from app.models.document import Document
from app.schemas.document_outline_item import DocumentOutlineItem
from app.schemas.recommendation import RecommendationSchema, RecommendationType
from app.models.recommendation_item import RecommendationItem
from app.schemas.recommendation import SnippetResponse, Snippet, Insight
from app.models.recommendation import Recommendation
from datetime import datetime

# Import services and core logic
from app.services.storage_service import StorageService
from app.services.insights_service import get_insight_service
from app.core.recommender import create_section_chunks, build_faiss_index, get_persona_recommendations, get_selection_recommendations
from app.core.insights import LLMManager, ProviderError
from app.core.index_manager import save_index, load_index

# Configure logger for this module
logger = logging.getLogger(__name__)

# Cache for FAISS indexes
INDEX_CACHE: dict[str, Tuple] = {}

class AnalysisRequest(BaseModel):
    persona: Optional[str] = None
    job_to_be_done: Optional[str] = None
    collection_ids: List[str]

class RecommenderService:
    """
    A service class for handling recommendation logic.

    This service manages the creation and updating of FAISS indexes for collections,
    generates persona-based and text-based recommendations using LLMs, and
    interacts with the database to store and retrieve recommendation records.
    """
    def __init__(self):
        self.llm_manager: Optional[LLMManager] = None
        try:
            self.llm_manager = LLMManager.from_env()
            logger.info("RecommenderService: LLMManager initialized successfully.")
        except Exception as e:
            logger.critical(f"RecommenderService: LLM Manager failed to initialize: {e}", exc_info=True)

    def _extract_json_from_markdown(self, text: str) -> str:
        """
        Extracts JSON string from a markdown code block.
        Assumes the JSON is within a ```json ... ``` block.

        Args:
            text (str): The input string, potentially containing a markdown JSON block.

        Returns:
            str: The extracted JSON string, or the original text if no markdown block is found.
        """
        logger.debug("RecommenderService: Attempting to extract JSON from markdown.")
        if text.strip().startswith("```json") and text.strip().endswith("```"):
            extracted_json = text.strip()[len("```json"): -len("```")].strip()
            logger.debug("RecommenderService: Successfully extracted JSON from markdown.")
            return extracted_json
        logger.debug("RecommenderService: No JSON markdown block found, returning original text.")
        return text

    def update_embeddings_for_collection(
        self,
        db: Session,
        storage_service: StorageService,
        collection_id: str
    ):
        """
        Creates or updates the FAISS index for an entire collection using the new core logic.

        This function retrieves all documents and their outline items for a given collection,
        creates text chunks, generates embeddings, and builds a FAISS index. The index
        and its mapping are then saved to disk and cached in memory.

        Args:
            db (Session): The SQLAlchemy database session.
            storage_service (StorageService): The storage service dependency for file operations.
            collection_id (str): The ID of the collection for which to update embeddings.
        """
        logger.info(f"RecommenderService: Starting embedding update for collection: {collection_id}")
        
        docs = db.query(Document).filter(Document.collectionId == collection_id).all()
        if not docs:
            logger.info(f"RecommenderService: No documents found for collection {collection_id}. Skipping embedding and cleaning up old index files.")
            try:
                (storage_service.artifacts_dir / f"collection_{collection_id}.faiss").unlink(missing_ok=True)
                (storage_service.artifacts_dir / f"collection_{collection_id}_map.pkl").unlink(missing_ok=True)
                logger.debug(f"RecommenderService: Removed old index files for {collection_id}.")
            except Exception as e:
                logger.warning(f"RecommenderService: Could not remove old index files for {collection_id}: {e}")
            return

        all_chunks = []
        processed_section_texts = set()
        logger.debug(f"RecommenderService: Processing {len(docs)} documents for collection {collection_id}.")
        for doc in docs:
            logger.debug(f"RecommenderService: Fetching outline items for document: {doc.id} - {doc.docName}")
            outline_items = db.query(DocumentOutlineItem).filter(DocumentOutlineItem.documentId == doc.id).all()
            
            outline_for_chunks = []
            for item in outline_items:
                section_content = item.section_text
                if section_content:
                    if section_content not in processed_section_texts:
                        outline_for_chunks.append({
                            "text": item.text,
                            "page": item.page,
                            "section_text": section_content,
                            "section_id": item.section_id,
                            "document_id": item.documentId
                        })
                        processed_section_texts.add(section_content)
                        logger.debug(f"RecommenderService: Added unique section_text for embedding: '{section_content[:100]}...'")
            
            logger.debug(f"RecommenderService: Calling create_section_chunks for document {doc.id}.")
            chunks = create_section_chunks(
                doc_id=doc.id,
                document_title=doc.docTitle,
                outline=outline_for_chunks,
                collection_id=collection_id
            )
            all_chunks.extend(chunks)
            logger.debug(f"RecommenderService: Added {len(chunks)} chunks from document {doc.id}. Total chunks so far: {len(all_chunks)}")

        if not all_chunks:
            logger.warning(f"RecommenderService: No text content found to embed for collection {collection_id}.")
            # Update isEmbeddingCreated status for all documents in the collection to FAILED if no chunks
            for doc in docs:
                doc.isEmbeddingCreated = "Failed"
                db.add(doc)
            db.commit()
            logger.info(f"RecommenderService: Set isEmbeddingCreated to FAILED for documents in collection {collection_id} due to no content.")
            return

        logger.info(f"RecommenderService: Building FAISS index with {len(all_chunks)} chunks for collection {collection_id}.")
        faiss_index, id_to_chunk_map = build_faiss_index(all_chunks)
        
        if faiss_index and id_to_chunk_map:
            logger.debug(f"RecommenderService: FAISS index and map built successfully. Saving artifacts for collection {collection_id}.")
            save_index(collection_id, faiss_index, id_to_chunk_map)
            INDEX_CACHE[collection_id] = (faiss_index, id_to_chunk_map)
            logger.info(f"RecommenderService: Successfully updated embeddings for collection {collection_id}.")
            for doc in docs:
                doc.isEmbeddingCreated = "Success"
                db.add(doc)
            db.commit()
            logger.debug(f"RecommenderService: Set isEmbeddingCreated to SUCCESS for documents in collection {collection_id}.")
        else:
            logger.error(f"RecommenderService: FAISS index or map was not built for collection {collection_id} (likely due to embedding failure).")
            for doc in docs:
                doc.isEmbeddingCreated = "Failed"
                db.add(doc)
            db.commit()
            logger.error(f"RecommenderService: Set isEmbeddingCreated to FAILED for documents in collection {collection_id}.")

    def _get_index_from_cache(self, collection_id: str, db: Session) -> Tuple[Optional[faiss.Index], Optional[Dict[int, Dict[str, Any]]]]:
        """
        Helper to load FAISS index and its mapping from cache or disk.

        Args:
            collection_id (str): The ID of the collection.
            db (Session): The SQLAlchemy database session (used for potential future re-build logic).

        Returns:
            Tuple[Optional[faiss.Index], Optional[Dict[int, Dict[str, Any]]]]: A tuple containing
            the FAISS index and the ID-to-chunk map, or (None, None) if not found.
        """
        logger.debug(f"RecommenderService: Attempting to get index for collection {collection_id} from cache.")
        if collection_id in INDEX_CACHE:
            logger.debug(f"RecommenderService: Index for collection {collection_id} found in cache.")
            return INDEX_CACHE[collection_id]

        logger.debug(f"RecommenderService: Index for collection {collection_id} not in cache, attempting to load from disk.")
        faiss_index, id_to_chunk_map = load_index(collection_id)
        if faiss_index and id_to_chunk_map:
            INDEX_CACHE[collection_id] = (faiss_index, id_to_chunk_map)
            logger.info(f"RecommenderService: Successfully loaded index for collection {collection_id} from disk and cached.")
            return faiss_index, id_to_chunk_map
        
        logger.warning(f"RecommenderService: Index not found for collection {collection_id} on disk. It might not have been built yet.")
        return None, None

    def find_relevant_snippets(
        self, 
        db: Session,
        storage_service: StorageService,
        selected_text: str,
        spanned_section_ids: List[str],
        collection_id: str
    ) -> SnippetResponse:
        """
        Orchestrates the synchronous, on-demand process of finding relevant
        snippets and generating insights based on a user's text selection.

        Args:
            db (Session): The SQLAlchemy database session.
            storage_service (StorageService): The storage service dependency.
            selected_text (str): The text selected by the user.
            spanned_section_ids (List[str]): The IDs of the structural sections the selection spans.
            collection_id (str): The ID of the collection to search within.

        Returns:
            SnippetResponse: A Pydantic model containing a list of relevant snippets and generated insights.

        Raises:
            HTTPException: 404 Not Found if embeddings index is not available for the collection.
            HTTPException: 503 Service Unavailable if the LLM service is not initialized.
        """
        logger.info(f"RecommenderService: Entering find_relevant_snippets for collection: {collection_id}, selected_text: '{selected_text[:50]}...'")

        faiss_index, id_to_chunk_map = self._get_index_from_cache(collection_id, db)
        if not faiss_index or not id_to_chunk_map:
            logger.error(f"RecommenderService: Embeddings index not found for collection {collection_id}.")
            raise HTTPException(status_code=404, detail=f"Embeddings index not found for collection {collection_id}. Please upload documents and ensure embeddings are created.")

        logger.debug(f"RecommenderService: Calling get_selection_recommendations with selected text for collection {collection_id}.")
        relevant_sections = get_selection_recommendations(
            selected_text=selected_text,
            faiss_index=faiss_index,
            id_to_chunk_map=id_to_chunk_map,
            num_results=5,
            collection_id=collection_id
        )
        logger.debug(f"RecommenderService: Found {len(relevant_sections)} relevant sections for collection {collection_id}.")

        if not relevant_sections:
            logger.info("RecommenderService: No relevant sections found, returning empty response.")
            return SnippetResponse(recommendations=[], insights=[])

        final_snippets = []
        context_for_insights = []

        logger.debug(f"RecommenderService: Processing {len(relevant_sections)} relevant sections for snippet extraction.")
        for i, section in enumerate(relevant_sections):
            logger.debug(f"RecommenderService: Processing section {i+1}/{len(relevant_sections)}: {section.get('section_title', 'N/A')}")
            
            if self.llm_manager:
                prompt_messages = [
                    {"role": "system", "content": "You are an expert research assistant. Explain why this text may be useful to a user."},
                    {"role": "user", "content": section['content'][:2000]}
                ]
                try:
                    section["snippet_explanation"] = self.llm_manager.get_response(prompt_messages)
                    logger.debug(f"RecommenderService: Generated explanation for snippet {i+1}.")
                except ProviderError as e:
                    section["snippet_explanation"] = f"Could not generate explanation: {e}"
                    logger.error(f"RecommenderService: Failed to generate explanation for snippet {i+1}: {e}", exc_info=True)
            else:
                section["snippet_explanation"] = "LLM service not available for explanation."
                logger.warning("RecommenderService: LLM service not available for snippet explanation.")

            snippet_data = {
                "document": section.get("document_name"),
                "section_title": section.get("section_title"),
                "page_number": section.get("page_number"),
                "content": section.get("content"),
                "snippet_explanation": section.get("snippet_explanation"),
                "collection_id": section.get("collection_id"),
                "_distance": section.get("_distance")
            }
            final_snippets.append(Snippet(**snippet_data))
            context_for_insights.append(f"Snippet from '{section.get('document_name')}': {section.get('content')[:150]} (Justification: {section.get('snippet_explanation')})")
            logger.debug(f"RecommenderService: Added snippet for section {i+1} to final_snippets and context_for_insights.")
        
        insights: List[Insight] = []
        if self.llm_manager:
            insight_context = "\n".join(context_for_insights)
            logger.debug(f"RecommenderService: Context for insights generated. Length: {len(insight_context)} characters.")
            insight_messages = [
                {"role": "system", "content": """You are an expert analyst. Based on the user's original text selection and the provided relevant snippets, generate a JSON array of high-level insights. Each insight object in the array must have a 'type' and 'text' field.
The 'type' field must be one of the following:
- "Key insights"
- "Did you know?"
- "Contradictions / counterpoints"
- "Inspirations or connections across docs"

Generate at least one insight for each type if applicable, or explain why it's not applicable. Ensure the output is a valid JSON array.
"""},
                {"role": "user", "content": f"User's original selection: '{selected_text}'\n\nHere are the most relevant snippets we found:\n---\n{insight_context}\n---"}
            ]
            
            logger.debug(f"RecommenderService: Calling LLM for insight generation.")
            llm_insights_response_str = self.llm_manager.get_response(insight_messages)
            logger.debug(f"RecommenderService: LLM response for insights (first 100 chars): {llm_insights_response_str[:100]}...")

            try:
                processed_llm_insights_response_str = self._extract_json_from_markdown(llm_insights_response_str)
                llm_insights_json = json.loads(processed_llm_insights_response_str)
                if isinstance(llm_insights_json, list):
                    for item in llm_insights_json:
                        if "type" in item and "text" in item:
                            insights.append(Insight(type=item["type"], text=item["text"]))
                        else:
                            logger.warning(f"RecommenderService: Malformed insight item received from LLM: {item}")
                else:
                    logger.warning(f"RecommenderService: LLM response for insights was not a list: {llm_insights_json}")
                    insights.append(Insight(type="generated_insight", text=llm_insights_response_str))
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"RecommenderService: Error parsing LLM response for insights: {e}", exc_info=True)
                insights.append(Insight(type="generated_insight", text=llm_insights_response_str))
        else:
            insights.append(Insight(type="service_unavailable", text="LLM service not available for insights."))
            logger.warning("RecommenderService: LLM service not available for insight generation.")

        logger.info(f"RecommenderService: Exiting find_relevant_snippets. Found {len(final_snippets)} snippets and {len(insights)} insights.")
        return SnippetResponse(recommendations=final_snippets, insights=insights)

    def run_analysis(self, request: AnalysisRequest, db: Session) -> RecommendationSchema:
        """
        Handles persona-based analysis requests and returns a RecommendationSchema.

        This function retrieves relevant content based on a persona or job-to-be-done,
        generates explanations for the snippets using an LLM, and stores the
        recommendation along with its items in the database.

        Args:
            request (AnalysisRequest): The request body containing persona or job-to-be-done.
            db (Session): The SQLAlchemy database session.

        Returns:
            RecommendationSchema: The newly created recommendation object.

        Raises:
            HTTPException: 503 Service Unavailable if the LLM service is not initialized.
            HTTPException: 404 Not Found if no recommendations are found.
        """
        logger.info(f"RecommenderService: Starting persona-based analysis for persona: '{request.persona}', job: '{request.job_to_be_done}'")
        if not self.llm_manager:
            logger.critical("RecommenderService: LLM service is not available. Cannot run analysis.")
            raise HTTPException(status_code=503, detail="LLM service is not available.")

        all_recommendation_items = []
        list_of_doc_ids_used = set()
        all_recs_data = []

        for coll_id in request.collection_ids:
            faiss_index, id_to_chunk_map = self._get_index_from_cache(coll_id, db)
            if not faiss_index or not id_to_chunk_map:
                logger.warning(f"RecommenderService.run_analysis: No FAISS index or map for collection {coll_id}. Skipping.")
                continue

            logger.debug(f"RecommenderService.run_analysis: Calling get_persona_recommendations for collection {coll_id}.")
            recs = get_persona_recommendations(
                persona=request.persona,
                job_to_be_done=request.job_to_be_done,
                faiss_index=faiss_index,
                id_to_chunk_map=id_to_chunk_map
            )
            logger.debug(f"RecommenderService.run_analysis: Received {len(recs)} raw recommendations from get_persona_recommendations for collection {coll_id}.")
            all_recs_data.extend(recs)
        
        if not all_recs_data:
            logger.warning(f"RecommenderService.run_analysis: No recommendation items found for persona/job-to-be-done, raising 404.")
            raise HTTPException(status_code=404, detail="No recommendations found for analysis.")

        prompt_template = {"role": "system", "content": "You are an expert research assistant. Provide a concise explanation (max 2 sentences) why this text may be useful to a user."}
        all_prompts = []
        for rec_data in all_recs_data:
            all_prompts.append([prompt_template, {"role": "user", "content": rec_data['snippet_text'][:2000]}])

        logger.debug(f"RecommenderService.run_analysis: Calling LLM in batch for {len(all_prompts)} explanations.")
        try:
            batch_explanations = self.llm_manager.get_responses_batch(all_prompts)
            logger.debug("RecommenderService.run_analysis: Batch LLM call for explanations completed.")
        except ProviderError as e:
            logger.error(f"RecommenderService.run_analysis: Batch LLM call for explanations failed: {e}", exc_info=True)
            batch_explanations = [f"Could not generate explanation: {e}"] * len(all_prompts)

        for i, rec_data in enumerate(all_recs_data):
            rec_data["snippet_explanation"] = str(batch_explanations[i]) if i < len(batch_explanations) else "Explanation generation failed."

            item_id = str(uuid.uuid4())
            doc_id = rec_data.get("doc_id", "unknown_doc")
            list_of_doc_ids_used.add(doc_id)

            item = RecommendationItem(
                item_id=item_id,
                recommendation_id="temp_rec_id",
                document_title=rec_data.get("document_title"),
                doc_id=doc_id,
                section_title=rec_data.get("section_title"),
                section_id=rec_data.get("section_id", str(uuid.uuid4())),
                page_number=rec_data.get("page_number"),
                snippet_text=rec_data.get("snippet_text"),
                snippet_explanation=rec_data.get("snippet_explanation"),
                annotation=None
            )
            all_recommendation_items.append(item)
        
        logger.debug(f"RecommenderService.run_analysis: Total recommendation items collected: {len(all_recommendation_items)}")

        recommendation_id = str(uuid.uuid4())
        generated_at = datetime.now()

        for item in all_recommendation_items:
            item.recommendation_id = recommendation_id

        db_recommendation = Recommendation(
            recommendation_id=recommendation_id,
            collection_id=request.collection_ids[0] if request.collection_ids else "unknown",
            user_selection_text=request.persona or request.job_to_be_done,
            spanned_section_ids=json.dumps([]),
            list_of_doc_ids_used=json.dumps(list(list_of_doc_ids_used)),
            latest_podcast_id=None,
            generated_at=generated_at,
            recommendation_type=RecommendationType.PERSONA,
            items=all_recommendation_items
        )
        db.add(db_recommendation)
        db.commit()
        db.refresh(db_recommendation)
        logger.info(f"RecommenderService.run_analysis: Saved Recommendation {recommendation_id} to DB with {len(db_recommendation.items)} items.")

        return RecommendationSchema.model_validate(db_recommendation, from_attributes=True)

    def get_selection_recommendations_api(
        self,
        db: Session,
        storage_service: StorageService,
        selected_text: str,
        collection_ids: List[str],
    ) -> RecommendationSchema:
        """
        Handles selection-based recommendation requests and returns a RecommendationSchema.

        This function finds relevant content based on a user's text selection within specified
        collections, generates explanations for the snippets using an LLM, and stores the
        recommendation along with its items in the database.

        Args:
            selected_text (str): The text selected by the user.
            collection_ids (List[str]): A list of collection IDs to search within.
            db (Session): The SQLAlchemy database session.

        Returns:
            RecommendationSchema: The newly created recommendation object.

        Raises:
            HTTPException: 503 Service Unavailable if the LLM service is not initialized.
            HTTPException: 400 Bad Request if selected text is empty.
            HTTPException: 404 Not Found if no recommendations are found.
        """
        logger.info(f"RecommenderService: Starting text-based recommendations for text: '{selected_text[:50]}...' in collections: {collection_ids}")
        if not self.llm_manager:
            logger.critical("RecommenderService: LLM service is not available. Cannot get selection recommendations.")
            raise HTTPException(status_code=503, detail="LLM service is not available.")
        if not selected_text.strip():
            logger.warning("RecommenderService: Selected text is empty for selection-based recommendations.")
            raise HTTPException(status_code=400, detail="Selected text cannot be empty.")

        all_recommendation_items = []
        list_of_doc_ids_used = set()
        all_recs_data = []

        for coll_id in collection_ids:
            faiss_index, id_to_chunk_map = self._get_index_from_cache(coll_id, db)
            if not faiss_index or not id_to_chunk_map:
                logger.warning(f"RecommenderService.get_selection_recommendations_api: No FAISS index or map for collection {coll_id}. Skipping.")
                continue

            logger.debug(f"RecommenderService.get_selection_recommendations_api: Calling get_selection_recommendations for collection {coll_id}.")
            recs = get_selection_recommendations(
                selected_text=selected_text,
                faiss_index=faiss_index,
                id_to_chunk_map=id_to_chunk_map,
                num_results=5
            )
            all_recs_data.extend(recs)
            
        if not all_recs_data:
            logger.warning("RecommenderService.get_selection_recommendations_api: No recommendations found for selection, raising 404.")
            raise HTTPException(status_code=404, detail="No recommendations found for selection.")

        prompt_template = {"role": "system", "content": "You are an expert research assistant. Provide a concise explanation (max 2 sentences) why this text may be useful to a user."}
        all_prompts = []
        for rec_data in all_recs_data:
            all_prompts.append([prompt_template, {"role": "user", "content": rec_data['snippet_text'][:2000]}])

        logger.debug(f"RecommenderService.get_selection_recommendations_api: Calling LLM in batch for {len(all_prompts)} explanations.")
        try:
            batch_explanations = self.llm_manager.get_responses_batch(all_prompts)
            logger.debug("RecommenderService.get_selection_recommendations_api: Batch LLM call for explanations completed.")
        except ProviderError as e:
            logger.error(f"RecommenderService.get_selection_recommendations_api: Batch LLM call for explanations failed: {e}", exc_info=True)
            batch_explanations = [f"Could not generate explanation: {e}"] * len(all_prompts)

        for i, rec_data in enumerate(all_recs_data):
            rec_data["snippet_explanation"] = str(batch_explanations[i]) if i < len(batch_explanations) else "Explanation generation failed."

            item_id = str(uuid.uuid4())
            doc_id = rec_data.get("doc_id", "unknown_doc")
            list_of_doc_ids_used.add(doc_id)

            quad_points = []
            page_number = rec_data.get("page_number")
            snippet_text = rec_data.get("snippet_text")

            if doc_id != "unknown_doc" and page_number is not None and snippet_text:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc and doc.docUrl:
                    # Extract relative path from doc.docUrl
                    base_url = settings.BASE_URL.rstrip('/')
                    relative_path = doc.docUrl.replace(f"{base_url}/storage/", "")
                    pdf_path = storage_service.get_absolute_path(relative_path)
                    if pdf_path.exists():
                        quad_points = get_quad_points_for_text(pdf_path, page_number - 1, snippet_text)
                    else:
                        logger.warning(f"RecommenderService: PDF file not found at {pdf_path} for doc_id {doc_id}.")
                else:
                    logger.warning(f"RecommenderService: Document or docUrl not found for doc_id {doc_id}.")

            item = RecommendationItem(
                item_id=item_id,
                recommendation_id="temp_rec_id",
                document_title=rec_data.get("document_title"),
                doc_id=doc_id,
                section_title=rec_data.get("section_title"),
                section_id=rec_data.get("section_id", str(uuid.uuid4())),
                page_number=page_number,
                snippet_text=snippet_text,
                snippet_explanation=rec_data.get("snippet_explanation"),
                annotation=None,
                quad_points=json.dumps(quad_points) # Add quad_points here
            )
            all_recommendation_items.append(item)

        recommendation_id = str(uuid.uuid4())
        generated_at = datetime.now()

        for item in all_recommendation_items:
            item.recommendation_id = recommendation_id

        db_recommendation = Recommendation(
            recommendation_id=recommendation_id,
            collection_id=collection_ids[0] if collection_ids else "unknown",
            user_selection_text=selected_text,
            spanned_section_ids=json.dumps([]),
            list_of_doc_ids_used=json.dumps(list(list_of_doc_ids_used)),
            latest_podcast_id=None,
            generated_at=generated_at,
            recommendation_type=RecommendationType.TEXT,
            items=all_recommendation_items
        )
        db.add(db_recommendation)
        db.commit()
        db.refresh(db_recommendation)
        logger.info(f"RecommenderService.get_selection_recommendations_api: Saved Recommendation {recommendation_id} to DB with {len(db_recommendation.items)} items.")

        return RecommendationSchema.model_validate(db_recommendation, from_attributes=True)

    def get_recommendations_for_collection(self, db: Session, collection_id: str) -> List[Recommendation]:
        """
        Retrieves all recommendation records for a specific collection.

        Args:
            db (Session): The SQLAlchemy database session.
            collection_id (str): The ID of the collection.

        Returns:
            List[Recommendation]: A list of SQLAlchemy Recommendation objects.
        """
        logger.debug(f"RecommenderService: Retrieving recommendations for collection ID: {collection_id}")
        recs = db.query(Recommendation).filter(Recommendation.collection_id == collection_id).all()
        logger.debug(f"RecommenderService: Retrieved {len(recs)} recommendations for collection {collection_id}.")
        return recs

    def get_recommendation_by_id(self, db: Session, recommendation_id: str) -> Optional[Recommendation]:
        """
        Retrieves a single recommendation record by its ID, including its items.
        Eagerly loads the 'items' relationship.

        Args:
            db (Session): The SQLAlchemy database session.
            recommendation_id (str): The ID of the recommendation to retrieve.

        Returns:
            Optional[Recommendation]: The SQLAlchemy Recommendation object if found, otherwise None.
        """
        logger.debug(f"RecommenderService: Retrieving recommendation with ID: {recommendation_id}")
        rec = db.query(Recommendation).options(joinedload(Recommendation.items)).filter(Recommendation.recommendation_id == recommendation_id).first()
        if rec:
            logger.debug(f"RecommenderService: Found recommendation with ID: {recommendation_id}.")
        else:
            logger.debug(f"RecommenderService: Recommendation with ID: {recommendation_id} not found.")
        return rec

    def delete_recommendations(self, db: Session, recommendation_ids: List[str]) -> int:
        """
        Deletes a list of recommendation records by their IDs.

        Args:
            db (Session): The SQLAlchemy database session.
            recommendation_ids (List[str]): A list of recommendation IDs to delete.

        Returns:
            int: The number of records deleted.
        """
        logger.info(f"RecommenderService: Deleting recommendations with IDs: {recommendation_ids}")
        num_deleted = db.query(Recommendation).filter(Recommendation.recommendation_id.in_(recommendation_ids)).delete(synchronize_session=False)
        db.commit()
        logger.info(f"RecommenderService: Successfully deleted {num_deleted} recommendation(s).")
        return num_deleted

# Create a single instance of the service
recommender_service = RecommenderService()

def get_recommender_service():
    """
    Dependency function to provide the recommender service instance.
    """
    return recommender_service
