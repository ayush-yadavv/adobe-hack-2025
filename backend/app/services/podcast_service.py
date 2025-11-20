import uuid
import json
import logging # Import logging
from typing import Optional, List
from datetime import datetime # Import datetime

from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException # Import HTTPException

# Import schemas and models
from app.models.podcast import Podcast # Import SQLAlchemy model
from app.models.recommendation import Recommendation # Import SQLAlchemy model
from app.models.recommendation_item import RecommendationItem # Import SQLAlchemy model
from app.models.document import Document # Import SQLAlchemy model
from app.models.collection import Collection # Import SQLAlchemy model
from app.schemas.document_outline_item import DocumentOutlineItem # This is a Pydantic schema
from app.schemas.podcast import PodcastGenerateRequest, PodcastInDB, PodcastScriptResponse # Import Pydantic PodcastInDB and new schemas
from app.models.insight import Insight as InsightModel # Import SQLAlchemy model

# Import services and core logic
from app.services.storage_service import StorageService
from app.core.insights import get_llm_response, get_llm_response_two_sentences, get_llm_response_json
from app.core.podcast import generate_audio
from app.core.pdf_parser import HybridPDFOutlineExtractor, get_pdf_parser

# Forward declaration for type hinting to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.insights_service import InsightService

# Configure logger for this module
logger = logging.getLogger(__name__)

class PodcastService:
    """
    A service class for handling podcast generation logic.

    This service orchestrates the generation of audio podcasts from various
    data sources (documents, collections, recommendations) using LLM-generated
    scripts and text-to-speech synthesis. It also manages podcast records
    in the database and interacts with the storage service.
    """

    def __init__(self, insights_service: "InsightService", pdf_parser: HybridPDFOutlineExtractor):
        self.insights_service = insights_service
        self.pdf_parser = pdf_parser
        logger.info("PodcastService initialized.")

    def _delete_old_podcasts(self, db: Session, source_id: str, source_type: str, storage_service: StorageService):
        """
        Deletes old podcast records associated with a specific source and their associated audio files.

        Args:
            db (Session): The SQLAlchemy database session.
            source_id (str): The ID of the source entity (document, collection, or recommendation).
            source_type (str): The type of the source entity.
            storage_service (StorageService): The storage service dependency for deleting files.
        """
        logger.debug(f"PodcastService: Deleting old podcasts for source {source_type} ID: {source_id}")
        old_podcasts = db.query(Podcast).filter(
            Podcast.sourceId == source_id,
            Podcast.sourceType == source_type
        ).all()

        for old_podcast in old_podcasts:
            if old_podcast.audioUrl:
                filename = old_podcast.audioUrl.split('/')[-1]
                storage_service.delete_podcast_file(filename)
                logger.debug(f"PodcastService: Deleted audio file: {filename}")
            db.delete(old_podcast)
            logger.debug(f"PodcastService: Deleted podcast record: {old_podcast.podcastId}")
        db.commit()
        logger.info(f"PodcastService: Finished deleting old podcasts for source {source_type} ID: {source_id}")

    def _delete_specific_podcast(self, db: Session, podcast_id: str, storage_service: StorageService):
        """
        Deletes a specific podcast record and its associated audio file.

        Args:
            db (Session): The SQLAlchemy database session.
            podcast_id (str): The ID of the podcast to delete.
            storage_service (StorageService): The storage service dependency for deleting files.
        """
        logger.debug(f"PodcastService: Deleting specific podcast ID: {podcast_id}")
        db_podcast = db.query(Podcast).filter(Podcast.podcastId == podcast_id).first()
        if db_podcast:
            if db_podcast.audioUrl:
                filename = db_podcast.audioUrl.split('/')[-1]
                storage_service.delete_podcast_file(filename)
                logger.debug(f"PodcastService: Deleted audio file for podcast {podcast_id}: {filename}")
            db.delete(db_podcast)
            db.commit()
            logger.info(f"PodcastService: Successfully deleted podcast record: {podcast_id}")
        else:
            logger.warning(f"PodcastService: Podcast with ID: {podcast_id} not found for deletion.")

    def generate_podcast_for_collection(
        self,
        db: Session,
        storage_service: StorageService,
        collection_id: str,
        podcast_in: PodcastGenerateRequest,
        include_insights: bool
    ) -> PodcastInDB:
        """
        Generates a podcast for an entire collection, combining content from its documents.

        Args:
            db (Session): The SQLAlchemy database session.
            storage_service (StorageService): The storage service dependency.
            collection_id (str): The ID of the collection to generate the podcast from.
            podcast_in (PodcastGenerateRequest): Request body containing podcast generation options.
            include_insights (bool): Flag to include insights in the podcast summary.

        Returns:
            PodcastInDB: The newly created podcast's details.

        Raises:
            Exception: If the collection is not found, or no readable content is found.
        """
        logger.info(f"PodcastService: Starting podcast generation for collection ID: {collection_id}")
        db_collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not db_collection:
            logger.error(f"PodcastService: Collection {collection_id} not found for podcast generation.")
            raise HTTPException(status_code=404, detail=f"Collection {collection_id} not found.")

        # Check if a completed podcast already exists for this collection
        if db_collection.latestPodcastId:
            existing_podcast = db.query(Podcast).filter(Podcast.podcastId == db_collection.latestPodcastId).first()
            if existing_podcast and existing_podcast.status == "completed":
                logger.info(f"PodcastService: Returning existing completed podcast {existing_podcast.podcastId} for collection {collection_id}.")
                return existing_podcast

        old_podcast_id = db_collection.latestPodcastId

        podcast_id = f"podcast_{uuid.uuid4().hex}"
        db_podcast = Podcast(
            podcastId=podcast_id,
            sourceId=collection_id,
            sourceType="collection",
            status="processing",
            generatedAt=datetime.now() # Set generatedAt immediately
        )
        db.add(db_podcast)
        db.commit()
        db.refresh(db_podcast) # Refresh to get the generatedAt timestamp

        try:
            documents = db.query(Document).filter(Document.collectionId == collection_id).all()
            if not documents:
                logger.warning(f"PodcastService: No documents found for collection {collection_id}.")
                raise HTTPException(status_code=400, detail=f"No documents found for collection {collection_id}.")

            full_collection_text = []
            for doc in documents:
                outline_items = db.query(DocumentOutlineItem).filter(DocumentOutlineItem.documentId == doc.id).all()
                if outline_items:
                    full_collection_text.append("\n".join([item.text for item in outline_items]))
                elif doc.docUrl:
                    try:
                        pdf_path = storage_service.get_document_path(doc.docUrl.split('/')[-1])
                        extracted_text = self.pdf_parser.extract_text_from_pdf(str(pdf_path))
                        full_collection_text.append(extracted_text)
                    except Exception as e:
                        logger.warning(f"PodcastService: Could not extract text from PDF for document {doc.id}: {e}")
                        pass
            
            if not full_collection_text:
                logger.warning(f"PodcastService: No readable content found for collection {collection_id}.")
                raise HTTPException(status_code=400, detail=f"No readable content found for collection {collection_id}.")

            script_context = "\n\n".join(full_collection_text)
            logger.debug(f"PodcastService: Collection {collection_id} script context length: {len(script_context)}")

            insights_text = None
            if include_insights:
                logger.debug(f"PodcastService: Attempting to include insights for collection {collection_id}.")
                if db_collection.latestInsightId:
                    db_insight = db.query(InsightModel).filter(InsightModel.insightId == db_collection.latestInsightId).first()
                    if db_insight and db_insight.insights_data:
                        parsed_insights = json.loads(db_insight.insights_data)
                        insights_text = "\n".join([item.get("data", "") for item in parsed_insights])
                        logger.debug(f"PodcastService: Using existing insight for collection {collection_id}.")
                
                if not insights_text: # Only generate new insights if latestInsightId is None or insight not found
                    logger.info(f"PodcastService: Generating new insights for collection {collection_id}.")
                    new_insight = self.insights_service.generate_and_store_insight(db=db, col_id=collection_id)
                    insights_text = "\n".join([item.data for item in new_insight.insights_data])
                    db_collection.latestInsightId = new_insight.insightId
                    db.add(db_collection)
                    db.commit()
                    logger.debug(f"PodcastService: Generated new insight {new_insight.insightId} for collection {collection_id}.")

                if insights_text:
                    script_context += f"\n\nKey Insights for Collection:\n{insights_text}"
                    logger.debug(f"PodcastService: Added insights to script context for collection {collection_id}.")

            min_words = podcast_in.min_duration_seconds / 60 * 150
            max_words = podcast_in.max_duration_seconds / 60 * 150
            logger.debug(f"PodcastService: Target word count for collection {collection_id}: {min_words}-{max_words} words.")

            script_messages = [
                {"role": "system", "content": (
                    f"You are a podcast host and a guest. Create an engaging, narrative-style audio script "
                    f"summarizing the following collection content. The script should be a dialogue between "
                    f"two distinct speakers, 'HOST' and 'GUEST'. Do NOT include any intro music cues, "
                    f"host greetings like 'Welcome back', or outro music cues. "
                    f"The total word count for the script should be approximately {int(min_words)}-{int(max_words)} words. "
                    f"Provide the output in JSON format, adhering to the following Pydantic schema:\n\n"
                    f"{PodcastScriptResponse.schema_json(indent=2)}"
                )},
                {"role": "user", "content": script_context}
            ]
            
            logger.debug(f"PodcastService: Calling LLM for script generation for collection {collection_id}.")
            podcast_response_json = get_llm_response_json(script_messages, response_model=PodcastScriptResponse)
            podcast_script_segments = podcast_response_json.script
            short_description = podcast_response_json.short_description
            logger.debug(f"PodcastService: LLM generated {len(podcast_script_segments)} script segments for collection {collection_id}.")

            db_podcast.transcript = [segment.model_dump() for segment in podcast_script_segments]

            output_filename = f"{podcast_id}.mp3" # Ensure unique filename
            output_path = storage_service.get_podcast_path(output_filename)
            
            from pydub import AudioSegment
            from app.core.podcast import create_podcast_from_script

            logger.debug(f"PodcastService: Generating audio for podcast {podcast_id} at {output_path}.")
            audio_file_path = create_podcast_from_script(script_segments=podcast_script_segments, output_file=str(output_path))
            
            audio = AudioSegment.from_mp3(audio_file_path)
            duration_seconds = len(audio) / 1000.0
            logger.debug(f"PodcastService: Audio generated for podcast {podcast_id}. Duration: {duration_seconds} seconds.")

            db_podcast.audioUrl = storage_service.get_file_url(f"podcasts/{output_filename}")
            db_podcast.shortDescription = short_description
            db_podcast.status = "completed"
            db_podcast.durationSeconds = int(duration_seconds)
            db_collection.latestPodcastId = podcast_id
            db.add(db_collection) # Add collection to session to mark as dirty
            db.commit()
            db.refresh(db_podcast)
            db.refresh(db_collection) # Refresh collection to reflect latestPodcastId

            if old_podcast_id:
                self._delete_specific_podcast(db, old_podcast_id, storage_service)
            
            logger.info(f"PodcastService: Successfully completed podcast generation for collection {collection_id}. Podcast ID: {podcast_id}")
            return db_podcast

        except Exception as e:
            logger.error(f"PodcastService: Failed to generate podcast for collection {collection_id}: {e}", exc_info=True)
            db_podcast.status = "failed"
            db_podcast.summary = f"Error: {str(e)}" # Use summary for error message
            db.commit()
            db.refresh(db_podcast)
            raise HTTPException(status_code=500, detail=f"Failed to generate podcast for collection {collection_id}: {str(e)}")

    def generate_podcast_for_document(
        self,
        db: Session,
        storage_service: StorageService,
        document_id: str,
        podcast_in: PodcastGenerateRequest,
        include_insights: bool
    ) -> PodcastInDB:
        """
        Generates a podcast for a single document.

        Args:
            db (Session): The SQLAlchemy database session.
            storage_service (StorageService): The storage service dependency.
            document_id (str): The ID of the document to generate the podcast from.
            podcast_in (PodcastGenerateRequest): Request body containing podcast generation options.
            include_insights (bool): Flag to include insights in the podcast summary.

        Returns:
            PodcastInDB: The newly created podcast's details.

        Raises:
            Exception: If the document is not found, or no readable content is found.
        """
        logger.info(f"PodcastService: Starting podcast generation for document ID: {document_id}")
        db_doc = db.query(Document).filter(Document.id == document_id).first()
        if not db_doc:
            logger.error(f"PodcastService: Document {document_id} not found for podcast generation.")
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

        # Check if a completed podcast already exists for this document
        if db_doc.latestPodcastId:
            existing_podcast = db.query(Podcast).filter(Podcast.podcastId == db_doc.latestPodcastId).first()
            if existing_podcast and existing_podcast.status == "completed":
                logger.info(f"PodcastService: Returning existing completed podcast {existing_podcast.podcastId} for document {document_id}.")
                return existing_podcast

        old_podcast_id = db_doc.latestPodcastId

        podcast_id = f"podcast_{uuid.uuid4().hex}"
        db_podcast = Podcast(
            podcastId=podcast_id,
            sourceId=document_id,
            sourceType="document",
            status="processing",
            generatedAt=datetime.now() # Set generatedAt immediately
        )
        db.add(db_podcast)
        db.commit()
        db.refresh(db_podcast)

        try:
            outline_items = db.query(DocumentOutlineItem).filter(DocumentOutlineItem.documentId == document_id).all()
            script_context = "\n".join([item.text for item in outline_items])
            
            if not script_context and db_doc.docUrl:
                try:
                    pdf_path = storage_service.get_document_path(db_doc.docUrl.split('/')[-1])
                    script_context = self.pdf_parser.extract_text_from_pdf(str(pdf_path))
                except Exception as e:
                    logger.warning(f"PodcastService: Could not extract text from PDF for document {db_doc.id}: {e}")
                    raise HTTPException(status_code=400, detail=f"Failed to extract content from document {document_id}.")

            if not script_context:
                logger.warning(f"PodcastService: No readable content found for document {document_id}.")
                raise HTTPException(status_code=400, detail=f"No readable content found for document {document_id}.")

            logger.debug(f"PodcastService: Document {document_id} script context length: {len(script_context)}")

            insights_text = None
            if include_insights:
                logger.debug(f"PodcastService: Attempting to include insights for document {document_id}.")
                if db_doc.latestInsightId:
                    db_insight = db.query(InsightModel).filter(InsightModel.insightId == db_doc.latestInsightId).first()
                    if db_insight and db_insight.insights_data:
                        parsed_insights = json.loads(db_insight.insights_data)
                        insights_text = "\n".join([item.get("data", "") for item in parsed_insights])
                        logger.debug(f"PodcastService: Using existing insight for document {document_id}.")
                
                if not insights_text: # Only generate new insights if latestInsightId is None or insight not found
                    logger.info(f"PodcastService: Generating new insights for document {document_id}.")
                    new_insight = self.insights_service.generate_and_store_insight(db=db, doc_id=document_id)
                    insights_text = "\n".join([item.data for item in new_insight.insights_data])
                    db_doc.latestInsightId = new_insight.insightId
                    db.add(db_doc)
                    db.commit()
                    logger.debug(f"PodcastService: Generated new insight {new_insight.insightId} for document {document_id}.")

                if insights_text:
                    script_context += f"\n\nKey Insights:\n{insights_text}"
                    logger.debug(f"PodcastService: Added insights to script context for document {document_id}.")

            min_words = podcast_in.min_duration_seconds / 60 * 150
            max_words = podcast_in.max_duration_seconds / 60 * 150
            logger.debug(f"PodcastService: Target word count for document {document_id}: {min_words}-{max_words} words.")

            script_messages = [
                {"role": "system", "content": (
                    f"You are a podcast host and a guest. Create an engaging, narrative-style audio script "
                    f"summarizing the following document content. The script should be a dialogue between "
                    f"two distinct speakers, 'HOST' and 'GUEST'. Do NOT include any intro music cues, "
                    f"host greetings like 'Welcome back', or outro music cues. "
                    f"The total word count for the script should be approximately {int(min_words)}-{int(max_words)} words. "
                    f"Provide the output in JSON format, adhering to the following Pydantic schema:\n\n"
                    f"{PodcastScriptResponse.schema_json(indent=2)}"
                )},
                {"role": "user", "content": script_context}
            ]
            
            logger.debug(f"PodcastService: Calling LLM for script generation for document {document_id}.")
            podcast_response_json = get_llm_response_json(script_messages, response_model=PodcastScriptResponse)
            podcast_script_segments = podcast_response_json.script
            short_description = podcast_response_json.short_description
            logger.debug(f"PodcastService: LLM generated {len(podcast_script_segments)} script segments for document {document_id}.")

            db_podcast.transcript = [segment.model_dump() for segment in podcast_script_segments]

            output_filename = f"{podcast_id}.mp3" # Ensure unique filename
            output_path = storage_service.get_podcast_path(output_filename)
            
            from pydub import AudioSegment
            from app.core.podcast import create_podcast_from_script

            logger.debug(f"PodcastService: Generating audio for podcast {podcast_id} at {output_path}.")
            audio_file_path = create_podcast_from_script(script_segments=podcast_script_segments, output_file=str(output_path))
            
            audio = AudioSegment.from_mp3(audio_file_path)
            duration_seconds = len(audio) / 1000.0
            logger.debug(f"PodcastService: Audio generated for podcast {podcast_id}. Duration: {duration_seconds} seconds.")

            db_podcast.audioUrl = storage_service.get_file_url(f"podcasts/{output_filename}")
            db_podcast.shortDescription = short_description
            db_podcast.status = "completed"
            db_podcast.durationSeconds = int(duration_seconds)
            db_doc.latestPodcastId = podcast_id
            db.add(db_doc) # Add document to session to mark as dirty
            db.commit()
            db.refresh(db_podcast)
            db.refresh(db_doc) # Refresh document to reflect latestPodcastId

            if old_podcast_id:
                self._delete_specific_podcast(db, old_podcast_id, storage_service)

            logger.info(f"PodcastService: Successfully completed podcast generation for document {document_id}. Podcast ID: {podcast_id}")
            return db_podcast

        except Exception as e:
            logger.error(f"PodcastService: Failed to generate podcast for document {document_id}: {e}", exc_info=True)
            db_podcast.status = "failed"
            db_podcast.summary = f"Error: {str(e)}"
            db.commit()
            db.refresh(db_podcast)
            raise HTTPException(status_code=500, detail=f"Failed to generate podcast for document {document_id}: {str(e)}")

    def generate_podcast_for_recommendation(
        self, 
        db: Session, 
        storage_service: StorageService,
        recommendation_id: str,
        podcast_in: PodcastGenerateRequest,
        include_insights: bool
    ) -> PodcastInDB:
        """
        Generates a podcast for a given recommendation event.

        Args:
            db (Session): The SQLAlchemy database session.
            storage_service (StorageService): The storage service dependency.
            recommendation_id (str): The ID of the recommendation to generate the podcast from.
            podcast_in (PodcastGenerateRequest): Request body containing podcast generation options.
            include_insights (bool): Flag to include insights in the podcast summary.

        Returns:
            PodcastInDB: The newly created podcast's details.

        Raises:
            Exception: If the recommendation is not found, or no snippets are found.
        """
        logger.info(f"PodcastService: Starting podcast generation for recommendation ID: {recommendation_id}")
        db_recommendation = db.query(Recommendation).filter(Recommendation.recommendation_id == recommendation_id).first()
        if not db_recommendation:
            logger.error(f"PodcastService: Recommendation record {recommendation_id} not found for podcast generation.")
            raise HTTPException(status_code=404, detail=f"Recommendation record {recommendation_id} not found.")

        # Check if a completed podcast already exists for this recommendation
        if db_recommendation.latest_podcast_id:
            existing_podcast = db.query(Podcast).filter(Podcast.podcastId == db_recommendation.latest_podcast_id).first()
            if existing_podcast and existing_podcast.status == "completed":
                logger.info(f"PodcastService: Returning existing completed podcast {existing_podcast.podcastId} for recommendation {recommendation_id}.")
                return existing_podcast

        old_podcast_id = db_recommendation.latest_podcast_id

        podcast_id = f"podcast_{uuid.uuid4().hex}"
        db_podcast = Podcast(
            podcastId=podcast_id,
            sourceId=recommendation_id,
            sourceType="recommendation",
            status="processing",
            generatedAt=datetime.now() # Set generatedAt immediately
        )
        db.add(db_podcast)
        db.commit()
        db.refresh(db_podcast)

        try:
            snippets = db.query(RecommendationItem).filter(RecommendationItem.recommendation_id == recommendation_id).all()
            if not snippets:
                logger.warning(f"PodcastService: No snippets found for recommendation {recommendation_id}.")
                raise HTTPException(status_code=400, detail=f"No snippets found for recommendation {recommendation_id}.")

            script_context = f"User's original selection: '{db_recommendation.user_selection_text}'\n\n"
            script_context += "Here are the relevant snippets and explanations found in the user's library:\n\n"
            for item in snippets:
                script_context += f"- From '{item.document_title}': {item.snippet_text} (Reason: {item.snippet_explanation})\n"
            
            logger.debug(f"PodcastService: Recommendation {recommendation_id} script context length: {len(script_context)}")

            insights_text = None
            if include_insights:
                logger.debug(f"PodcastService: Attempting to include insights for recommendation {recommendation_id}.")
                if db_recommendation.latest_insight_id:
                    db_insight = db.query(InsightModel).filter(InsightModel.insightId == db_recommendation.latest_insight_id).first()
                    if db_insight and db_insight.insights_data:
                        parsed_insights = json.loads(db_insight.insights_data)
                        insights_text = "\n".join([item.get("data", "") for item in parsed_insights])
                        logger.debug(f"PodcastService: Using existing insight for recommendation {recommendation_id}.")
                
                if not insights_text: # Only generate new insights if latest_insight_id is None or insight not found
                    logger.info(f"PodcastService: Generating new insights for recommendation {recommendation_id}.")
                    new_insight = self.insights_service.generate_and_store_insight(db=db, rec_id=recommendation_id)
                    insights_text = "\n".join([item.data for item in new_insight.insights_data])
                    db_recommendation.latest_insight_id = new_insight.insightId
                    db.add(db_recommendation)
                    db.commit()
                    logger.debug(f"PodcastService: Generated new insight {new_insight.insightId} for recommendation {recommendation_id}.")

                if insights_text:
                    script_context += f"\n\nOverall Insight:\n{insights_text}"
                    logger.debug(f"PodcastService: Added insights to script context for recommendation {recommendation_id}.")

            min_words = podcast_in.min_duration_seconds / 60 * 150
            max_words = podcast_in.max_duration_seconds / 60 * 150
            logger.debug(f"PodcastService: Target word count for recommendation {recommendation_id}: {min_words}-{max_words} words.")

            script_messages = [
                {"role": "system", "content": (
                    f"You are a podcast host and a guest. Create an engaging, narrative-style audio script "
                    f"summarizing the following recommendation content. The script should be a dialogue between "
                    f"two distinct speakers, 'HOST' and 'GUEST'. Do NOT include any intro music cues, "
                    f"host greetings like 'Welcome back', or outro music cues. "
                    f"The total word count for the script should be approximately {int(min_words)}-{int(max_words)} words. "
                    f"Provide the output in JSON format, adhering to the following Pydantic schema:\n\n"
                    f"{PodcastScriptResponse.schema_json(indent=2)}"
                )},
                {"role": "user", "content": f"Please create a podcast script from the following information:\n\n---\n{script_context}\n---"}
            ]
            
            logger.debug(f"PodcastService: Calling LLM for script generation for recommendation {recommendation_id}.")
            podcast_response_json = get_llm_response_json(script_messages, response_model=PodcastScriptResponse)
            podcast_script_segments = podcast_response_json.script
            short_description = podcast_response_json.short_description
            logger.debug(f"PodcastService: LLM generated {len(podcast_script_segments)} script segments for recommendation {recommendation_id}.")

            db_podcast.transcript = [segment.model_dump() for segment in podcast_script_segments]

            output_filename = f"{podcast_id}.mp3" # Ensure unique filename
            output_path = storage_service.get_podcast_path(output_filename)
            
            from pydub import AudioSegment
            from app.core.podcast import create_podcast_from_script

            logger.debug(f"PodcastService: Generating audio for podcast {podcast_id} at {output_path}.")
            audio_file_path = create_podcast_from_script(script_segments=podcast_script_segments, output_file=str(output_path))
            
            audio = AudioSegment.from_mp3(audio_file_path)
            duration_seconds = len(audio) / 1000.0
            logger.debug(f"PodcastService: Audio generated for podcast {podcast_id}. Duration: {duration_seconds} seconds.")

            db_podcast.audioUrl = storage_service.get_file_url(f"podcasts/{output_filename}")
            db_podcast.shortDescription = short_description
            db_podcast.status = "completed"
            db_podcast.durationSeconds = int(duration_seconds)
            db_recommendation.latest_podcast_id = podcast_id
            db.add(db_recommendation) # Add recommendation to session to mark as dirty
            db.commit()
            db.refresh(db_podcast)
            db.refresh(db_recommendation) # Refresh recommendation to reflect latest_podcast_id

            if old_podcast_id:
                self._delete_specific_podcast(db, old_podcast_id, storage_service)

            logger.info(f"PodcastService: Successfully completed podcast generation for recommendation {recommendation_id}. Podcast ID: {podcast_id}")
            return db_podcast

        except Exception as e:
            logger.error(f"PodcastService: Failed to generate podcast for recommendation {recommendation_id}: {e}", exc_info=True)
            db_podcast.status = "failed"
            db_podcast.summary = f"Error: {str(e)}"
            db.commit()
            db.refresh(db_podcast)
            raise HTTPException(status_code=500, detail=f"Failed to generate podcast for recommendation {recommendation_id}: {str(e)}")

def get_podcast_service(
    insights_service: "InsightService" = Depends(lambda: __import__("app.services.insights_service", fromlist=["get_insight_service"]).get_insight_service()),
    pdf_parser: HybridPDFOutlineExtractor = Depends(get_pdf_parser)
):
    """
    Dependency function to provide the podcast service instance.
    """
    return PodcastService(insights_service, pdf_parser)
