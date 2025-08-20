import os
import pickle
from pathlib import Path
import faiss
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.models.collection import Collection # Import from models
from app.models.document import Document # Import from models
from app.core.recommender import create_section_chunks, build_faiss_index

# Directory to store FAISS indexes and metadata
INDEX_DIR = Path("storage/artifacts") # Changed to storage/artifacts
INDEX_DIR.mkdir(parents=True, exist_ok=True)


def save_index(collection_id: int, index, id_to_chunk_map: dict):
    """
    Save FAISS index and metadata for a given collection.
    - collection_id: ID of the collection this index belongs to.
    - index: FAISS index object.
    - id_to_chunk_map: Dictionary mapping FAISS IDs -> section/chunk metadata.
    """
    index_path = INDEX_DIR / f"collection_{collection_id}.faiss"
    map_path = INDEX_DIR / f"collection_{collection_id}_map.pkl"

    faiss.write_index(index, str(index_path))
    with open(map_path, "wb") as f:
        pickle.dump(id_to_chunk_map, f)

    print(f"[IndexManager] Saved index for collection {collection_id} at {index_path}")


def load_index(collection_id: int):
    """
    Load FAISS index and metadata for a given collection.
    Returns:
        (index, id_to_chunk_map)
        or (None, None) if files are missing.
    """
    index_path = INDEX_DIR / f"collection_{collection_id}.faiss"
    map_path = INDEX_DIR / f"collection_{collection_id}_map.pkl"

    if not index_path.exists() or not map_path.exists():
        print(f"[IndexManager] No saved index found for collection {collection_id}")
        return None, None

    index = faiss.read_index(str(index_path))
    with open(map_path, "rb") as f:
        id_to_chunk_map = pickle.load(f)

    print(f"[IndexManager] Loaded index for collection {collection_id}")
    return index, id_to_chunk_map


def delete_index(collection_id: int):
    """
    Delete FAISS index and metadata for a given collection (if exists).
    Useful when a collection is deleted or re-uploaded.
    """
    index_path = INDEX_DIR / f"collection_{collection_id}.faiss"
    map_path = INDEX_DIR / f"collection_{collection_id}_map.pkl"

    removed = False
    for path in [index_path, map_path]:
        if path.exists():
            path.unlink()
            removed = True

    if removed:
        print(f"[IndexManager] Deleted index for collection {collection_id}")
    else:
        print(f"[IndexManager] No index to delete for collection {collection_id}")


def build_and_save_collection_index(collection_id: int, db: Session):
    all_chunks = []
    statement = select(Collection).where(Collection.id == collection_id).options(
        selectinload(Collection.documents).selectinload(Document.outline_items) # Use Document and outline_items
    )
    collection = db.exec(statement).first()
    if not collection:
        print(f"[IndexManager] Collection {collection_id} not found.")
        return

    for doc in collection.documents:
        outline_from_db = [
            {"text": s.text, "page": s.page, "section_text": s.section_text, "section_id": s.section_id} 
            for s in doc.outline_items
        ]
        chunks = create_section_chunks(doc_id=doc.id, document_title=doc.docTitle, outline=outline_from_db, collection_id=collection_id)
        all_chunks.extend(chunks)

    if not all_chunks:
        print(f"[IndexManager] No content to index for collection {collection_id}")
        return

    faiss_index, id_to_chunk_map = build_faiss_index(all_chunks)
    if faiss_index and id_to_chunk_map:
        save_index(collection_id, faiss_index, id_to_chunk_map)
        # Note: INDEX_CACHE is in recommendation.py, not here.
        # The calling function will update its cache.
