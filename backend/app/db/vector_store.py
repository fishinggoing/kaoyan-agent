"""
ChromaDB vector store for semantic school/major search.

Uses ONNX-based DefaultEmbeddingFunction (all-MiniLM-L6-v2) when available.
The model downloads automatically on first use (~79MB from HuggingFace).
If the download fails (e.g., network restrictions), the vector search is
unavailable but SQL-based multi-field relevance search still works via
the /api/schools/search endpoint.
"""

import logging

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)

_chroma_client = None  # type: chromadb.PersistentClient | None
_embedding_fn = None


def _get_embedding_fn():
    global _embedding_fn
    if _embedding_fn is None:
        try:
            from chromadb.utils import embedding_functions
            _embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        except Exception as e:
            logger.warning(f"ChromaDB embedding function unavailable: {e}")
            _embedding_fn = False
    return _embedding_fn if _embedding_fn is not False else None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_school_collection():
    client = get_chroma_client()
    ef = _get_embedding_fn()
    return client.get_or_create_collection(
        name="schools",
        metadata={"description": "院校信息向量索引"},
        embedding_function=ef,
    )


def get_major_collection():
    client = get_chroma_client()
    ef = _get_embedding_fn()
    return client.get_or_create_collection(
        name="majors",
        metadata={"description": "专业信息向量索引"},
        embedding_function=ef,
    )


def index_schools(schools: list[dict]) -> int:
    """Index a batch of school documents into ChromaDB.

    Returns the number of documents indexed, or 0 if embeddings are unavailable.
    """
    if _get_embedding_fn() is None:
        logger.warning("Cannot index schools: embedding function unavailable")
        return 0

    try:
        col = get_school_collection()
        ids = [f"school_{s['id']}" for s in schools]
        docs = [
            f"{s.get('name', '')} {s.get('province', '')} {s.get('city', '')} "
            f"{s.get('description', '') or ''}"[:500]
            for s in schools
        ]
        metadatas = [
            {"school_id": s["id"], "name": s.get("name", ""),
             "province": s.get("province", ""), "level": str(s.get("level", ""))}
            for s in schools
        ]
        col.upsert(ids=ids, documents=docs, metadatas=metadatas)
        return len(schools)
    except Exception as e:
        logger.error(f"Failed to index schools: {e}")
        return 0


def search_schools_vector(query: str, top_k: int = 10) -> list[dict]:
    """Semantic search over indexed schools. Returns empty list if unavailable."""
    if _get_embedding_fn() is None:
        return []

    try:
        col = get_school_collection()
        if col.count() == 0:
            return []
        results = col.query(query_texts=[query], n_results=min(top_k, col.count()))
        if not results or not results.get("ids") or not results["ids"][0]:
            return []
        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            dist = results["distances"][0][i] if results.get("distances") else 0
            items.append({
                "school_id": meta.get("school_id"),
                "name": meta.get("name", ""),
                "relevance": round(1.0 - min(dist, 1.0), 3) if dist else 0,
            })
        return items
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []
