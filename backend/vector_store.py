from __future__ import annotations
import re
import chromadb
from backend.config import CHROMA_PERSIST_DIR

_client: chromadb.PersistentClient | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    sanitized = sanitized[:63]
    if len(sanitized) < 3:
        sanitized = sanitized + "_kb"
    return sanitized


def store_paragraphs(
    collection_name: str,
    paragraphs: list[str],
    embeddings: list[list[float]],
    source_url: str,
    page_title: str,
) -> int:
    client = _get_client()
    name = _sanitize_name(collection_name)
    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
    ids = [f"{source_url}#{i}" for i in range(len(paragraphs))]
    metadatas = [{"source_url": source_url, "page_title": page_title, "para_index": i}
                 for i in range(len(paragraphs))]
    collection.upsert(ids=ids, embeddings=embeddings, documents=paragraphs, metadatas=metadatas)
    return len(paragraphs)


def search_collection(
    collection_name: str,
    query_embedding: list[float],
    n_results: int = 5,
) -> list[dict]:
    client = _get_client()
    name = _sanitize_name(collection_name)
    try:
        collection = client.get_collection(name=name)
    except Exception:
        return []
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source_url": meta.get("source_url", ""),
            "page_title": meta.get("page_title", ""),
            "score": round(1 - dist, 4),
        })
    return chunks


def list_collections() -> list[str]:
    client = _get_client()
    return [c.name for c in client.list_collections()]


def delete_collection(name: str) -> bool:
    client = _get_client()
    sanitized = _sanitize_name(name)
    try:
        client.delete_collection(sanitized)
        return True
    except Exception:
        return False
