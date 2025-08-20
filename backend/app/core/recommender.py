# In backend/core/recommender.py

import faiss
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from typing import Optional, Set
import re
from sklearn.metrics.pairwise import cosine_similarity

# This local model is used for the core recommendation feature to meet the CPU-only constraint.
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
model = SentenceTransformer(MODEL_NAME)

SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')


def extract_snippet(text: str, max_sentences: int = 3, fallback_chars: int = 350) -> str:
    if not text:
        return ""
    # Prefer first 2–3 sentences
    sentences = SENTENCE_SPLIT.split(text.strip())
    if sentences:
        return " ".join(sentences[:max_sentences]).strip()
    # Fallback to trimmed chunk
    return text[:fallback_chars].strip() + ("..." if len(text) > fallback_chars else "")


# --- Functions for Building the Search Index ---

def create_section_chunks(doc_id: str, document_title: str, outline: list, collection_id: str) -> list:
    """
    Transforms the detailed outline from the parser into the "chunk" format
    needed for the FAISS index.
    """
    chunks_with_metadata = []
    for section in outline:
        section_content = section.get("section_text", "")
        if section_content:
            chunks_with_metadata.append({
                'document_id': doc_id,
                'document_title': document_title,
                'page_number': section.get("page"),
                'section_title': section.get("text"),
                'section_id': section.get("section_id"),
                'content': section_content,
                'collection_id': collection_id
            })
    return chunks_with_metadata


def build_faiss_index(chunks_with_metadata: list) -> tuple:
    """
    Encodes text chunks and builds a FAISS index.
    Returns the index and a mapping from index ID to chunk metadata.
    """
    if not chunks_with_metadata:
        return None, None

    contents = [chunk['content'] for chunk in chunks_with_metadata]
    embeddings = model.encode(contents, show_progress_bar=True)

    embedding_dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(embedding_dimension)
    index.add(np.array(embeddings).astype('float32'))

    id_to_chunk_map = {i: chunk for i, chunk in enumerate(chunks_with_metadata)}

    return index, id_to_chunk_map


# --- Helper Functions for Deduplication ---

def calculate_text_similarity(text1: str, text2: str, threshold: float = 0.8) -> bool:
    """Calculate if two texts are too similar using embeddings."""
    if not text1 or not text2:
        return False

    embeddings = model.encode([text1, text2])
    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    return similarity > threshold


def is_content_too_similar(selected_text: str, candidate_text: str,
                           similarity_threshold: float = 0.85) -> bool:
    """Check if candidate content is too similar to selected text."""
    # Exact match check
    if selected_text.strip() == candidate_text.strip():
        return True

    # Length-based quick filter
    if abs(len(selected_text) - len(candidate_text)) < 50:
        return calculate_text_similarity(selected_text, candidate_text, similarity_threshold)

    return False


def deduplicate_recommendations(recommendations: list,
                                similarity_threshold: float = 0.75) -> list:
    """Remove duplicate or highly similar recommendations."""
    if not recommendations:
        return []

    unique_recommendations = []
    seen_content: Set[str] = set()
    seen_sections: Set[tuple] = set()

    for rec in recommendations:
        # Skip exact duplicates by section
        section_key = (rec.get('doc_id'), rec.get('section_id'))
        if section_key in seen_sections:
            continue

        # Skip if content is too similar to already selected content
        content = rec.get('full_section_text', '')
        is_duplicate = False

        for existing_content in seen_content:
            if calculate_text_similarity(content, existing_content, similarity_threshold):
                is_duplicate = True
                break

        if not is_duplicate:
            unique_recommendations.append(rec)
            seen_content.add(content)
            seen_sections.add(section_key)

    return unique_recommendations


# --- Functions for Getting Recommendations ---

def get_selection_recommendations(
        selected_text: str,
        faiss_index: faiss.Index,
        id_to_chunk_map: dict,
        num_results: int = 5,
        collection_id: Optional[str] = None,
        similarity_threshold: float = 0.85,
        max_results_multiplier: int = 3
) -> list:
    """
    Get recommendations based on selected text with improved deduplication.
    """
    if not selected_text or not faiss_index or not id_to_chunk_map:
        return []

    # Get more results initially to account for filtering
    search_count = min(num_results * max_results_multiplier, len(id_to_chunk_map))

    query_embedding = model.encode([selected_text])
    distances, indices = faiss_index.search(np.array(query_embedding), search_count)

    recommendations = []
    processed_sections: Set[tuple] = set()  # Track (doc_id, section_id) pairs

    for dist, idx in zip(distances[0], indices[0]):
        if len(recommendations) >= num_results:
            break

        retrieved_chunk = id_to_chunk_map.get(int(idx))
        if not retrieved_chunk:
            continue

        # Filter by collection_id if provided
        if collection_id and retrieved_chunk.get('collection_id') != collection_id:
            continue

        # Skip if we've already processed this section
        section_key = (retrieved_chunk.get('document_id'), retrieved_chunk.get('section_id'))
        if section_key in processed_sections:
            continue

        candidate_content = retrieved_chunk['content']

        # Skip if content is too similar to selected text
        if is_content_too_similar(selected_text, candidate_content, similarity_threshold):
            continue

        # Add to recommendations
        rec = {
            "document_title": retrieved_chunk.get('document_title'),
            "doc_id": retrieved_chunk.get('document_id'),
            "section_title": retrieved_chunk.get('section_title'),
            "section_id": retrieved_chunk.get('section_id'),
            "page_number": retrieved_chunk.get('page_number'),
            "snippet_text": extract_snippet(candidate_content),
            "full_section_text": candidate_content,
            "collection_id": retrieved_chunk.get('collection_id'),
            "_distance": float(dist)
        }

        recommendations.append(rec)
        processed_sections.add(section_key)

    # Final deduplication pass for content similarity
    return deduplicate_recommendations(recommendations)


def get_persona_recommendations(
        persona: str,
        job_to_be_done: str,
        faiss_index: faiss.Index,
        id_to_chunk_map: dict,
        num_results: int = 5,
        collection_id: Optional[str] = None,
        max_results_multiplier: int = 2
) -> list:
    """
    (EXTENDED FEATURE) Finds relevant sections based on a persona and job to be done.
    Returns recommendations along with FAISS distance scores.
    """
    if not persona or not job_to_be_done or not faiss_index or not id_to_chunk_map:
        return []

    # Build query string
    query = f"Persona: {persona}. Task: {job_to_be_done}"

    # Get more results initially to account for filtering
    search_count = min(num_results * max_results_multiplier, len(id_to_chunk_map))

    query_embedding = model.encode([query])
    distances, indices = faiss_index.search(np.array(query_embedding), search_count)

    recommendations = []
    processed_sections: Set[tuple] = set()

    for dist, idx in zip(distances[0], indices[0]):
        if len(recommendations) >= num_results:
            break

        retrieved_chunk = id_to_chunk_map.get(int(idx))
        if not retrieved_chunk:
            continue

        # Filter by collection_id if provided
        if collection_id and retrieved_chunk.get('collection_id') != collection_id:
            continue

        # Skip if we've already processed this section
        section_key = (retrieved_chunk.get('document_id'), retrieved_chunk.get('section_id'))
        if section_key in processed_sections:
            continue

        rec = {
            "document_title": retrieved_chunk.get('document_title'),
            "doc_id": retrieved_chunk.get('document_id'),
            "section_title": retrieved_chunk.get('section_title'),
            "section_id": retrieved_chunk.get('section_id'),
            "page_number": retrieved_chunk.get('page_number'),
            "snippet_text": extract_snippet(retrieved_chunk['content']),
            "full_section_text": retrieved_chunk['content'],
            "collection_id": retrieved_chunk.get('collection_id'),
            "_distance": float(dist)
        }

        recommendations.append(rec)
        processed_sections.add(section_key)

    # Final deduplication pass
    return deduplicate_recommendations(recommendations)