"""
Embedding index module for AI Doc Generator.

Manages semantic embeddings for code chunks using Gemini's
text-embedding-004 model and FAISS for fast similarity search.
Includes a persistent JSON cache to avoid re-embedding unchanged code.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import faiss
from google import genai

from clients import get_gemini_client, gemini_retry
from config import settings
from logger import setup_logger
from chunking.code_chunker import CodeChunk
from core.utils import save_json_locked

logger = setup_logger("embeddings")

EMBEDDING_DIM = 3072  # gemini-embedding-001 dimension


@dataclass
class EmbeddingStore:
    """
    In-memory FAISS index with metadata tracking.

    Attributes:
        index: FAISS flat L2 index.
        chunks: Ordered list of stored CodeChunk objects.
        cache: Dict mapping text hash → embedding vector.
        cache_path: Path to persist the embedding cache.
    """

    index: faiss.IndexFlatL2 = field(
        default_factory=lambda: faiss.IndexFlatL2(EMBEDDING_DIM)
    )
    chunks: list[CodeChunk] = field(default_factory=list)
    cache: dict[str, list[float]] = field(default_factory=dict)
    cache_path: Path = field(
        default_factory=lambda: Path(settings.embedding_cache_file)
    )

    def __post_init__(self) -> None:
        """Load embedding cache from disk if it exists."""
        self._load_cache()

    def _load_cache(self) -> None:
        """Load the on-disk embedding cache into memory."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path) as f:
                    self.cache = json.load(f)
                logger.info("Loaded %d cached embeddings from %s", len(self.cache), self.cache_path)
            except Exception as exc:
                logger.warning("Failed to load embedding cache: %s", exc)
                self.cache = {}

    def _save_cache(self) -> None:
        """Persist the in-memory embedding cache to disk safely."""
        save_json_locked(self.cache_path, self.cache)


# Global embedding store singleton
_store: EmbeddingStore | None = None


def get_store() -> EmbeddingStore:
    """Return the global EmbeddingStore, creating it if needed."""
    global _store
    if _store is None:
        _store = EmbeddingStore()
    return _store


def _text_hash(text: str) -> str:
    """Compute a stable SHA256 hash for a text string."""
    return hashlib.sha256(text.encode()).hexdigest()


@gemini_retry
def create_embedding(text: str) -> np.ndarray:
    """
    Generate a semantic embedding vector for a text string.

    Results are cached by content hash to avoid redundant API calls.

    Args:
        text: Source code or natural language text to embed.

    Returns:
        A float32 numpy array of shape (EMBEDDING_DIM,).

    Raises:
        Exception: If the API call fails.

    Example:
        >>> vec = create_embedding("def login(user, password): ...")
        >>> print(vec.shape)
        (768,)
    """
    store = get_store()
    key = _text_hash(text)

    if key in store.cache:
        logger.debug("Cache hit for embedding (hash=%s...)", key[:8])
        return np.array(store.cache[key], dtype=np.float32)

    client = get_gemini_client()
    response = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=text[:8000],  # token limit guard
    )
    vector = response.embeddings[0].values
    store.cache[key] = vector
    logger.debug("Created new embedding (hash=%s...)", key[:8])
    return np.array(vector, dtype=np.float32)


def store_embedding(chunk: CodeChunk) -> None:
    """
    Generate and store an embedding for a code chunk in the FAISS index.

    The chunk is appended to the store's metadata list at the same index
    position as the FAISS vector.

    Args:
        chunk: A :class:`CodeChunk` to embed and store.

    Example:
        >>> store_embedding(CodeChunk(type="function", name="login", ...))
    """
    store = get_store()
    text = _chunk_to_text(chunk)
    vector = create_embedding(text)

    vec_2d = vector.reshape(1, -1)
    store.index.add(vec_2d)
    store.chunks.append(chunk)


def build_index(chunks: list[CodeChunk], batch_size: int = 50) -> None:
    """
    Embed and index all chunks, persisting the cache at the end.

    Args:
        chunks: All code chunks to embed and store.
        batch_size: Log progress every N chunks.

    Example:
        >>> build_index(all_chunks)
        >>> print(f"Index size: {get_store().index.ntotal}")
    """
    store = get_store()
    logger.info("Building embedding index for %d chunks...", len(chunks))

    for i, chunk in enumerate(chunks, 1):
        try:
            store_embedding(chunk)
        except Exception as exc:
            logger.warning("Failed to embed chunk %s: %s", chunk.id, exc)

        if i % batch_size == 0:
            logger.info("Embedded %d / %d chunks", i, len(chunks))
            store._save_cache()

    store._save_cache()
    logger.info("Index complete: %d vectors stored.", store.index.ntotal)


def search_similar(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Search for the top-k most semantically similar chunks to a query.

    Args:
        query: Natural language or code query string.
        top_k: Number of results to return.

    Returns:
        List of dicts with keys: ``chunk`` (CodeChunk), ``score`` (float),
        ``rank`` (int).

    Example:
        >>> results = search_similar("authentication and login logic")
        >>> print(results[0]["chunk"].name)
        login
    """
    store = get_store()
    if store.index.ntotal == 0:
        logger.warning("Embedding index is empty — no search results.")
        return []

    query_vec = create_embedding(query).reshape(1, -1)
    distances, indices = store.index.search(query_vec, min(top_k, store.index.ntotal))

    results = []
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < 0:
            continue
        results.append({
            "chunk": store.chunks[idx],
            "score": float(dist),
            "rank": rank + 1,
        })
    return results


def reset_store() -> None:
    """Reset the global embedding store (useful for testing)."""
    global _store
    _store = EmbeddingStore()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chunk_to_text(chunk: CodeChunk) -> str:
    """Build a searchable text representation of a chunk for embedding."""
    parts = [
        f"File: {chunk.file}",
        f"Language: {chunk.language}",
        f"Type: {chunk.type}",
        f"Name: {chunk.name}",
    ]
    if chunk.parent_class:
        parts.append(f"Class: {chunk.parent_class}")
    parts.append("")
    parts.append(chunk.code[:4000])
    return "\n".join(parts)
