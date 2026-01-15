"""Embedding service using Fireworks AI via OpenAI SDK."""

import asyncio
from typing import Literal

from openai import AsyncOpenAI

from app.config import settings

EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768
RERANK_MODEL = "accounts/fireworks/models/qwen3-reranker-8b"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"

# Singleton client - reused across requests
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Get or create the async OpenAI client configured for Fireworks."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.fireworks_api_key,
            base_url=FIREWORKS_BASE_URL,
        )
    return _client


async def embed_document(text: str) -> list[float]:
    """Generate embedding for a document (for storage/indexing)."""
    if not text.strip():
        raise ValueError("Cannot embed empty text")

    client = _get_client()
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=f"search_document: {text}",
    )
    return response.data[0].embedding


async def embed_query(text: str) -> list[float]:
    """Generate embedding for a search query."""
    if not text.strip():
        raise ValueError("Cannot embed empty query")

    client = _get_client()
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=f"search_query: {text}",
    )
    return response.data[0].embedding


async def embed_documents_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of documents."""
    if not texts:
        return []

    client = _get_client()
    prefixed = [f"search_document: {t}" for t in texts]
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=prefixed,
    )
    return [item.embedding for item in response.data]


async def rerank(query: str, documents: list[str], top_k: int = 15) -> list[tuple[int, float]]:
    """Rerank documents using Qwen3 reranker via Fireworks AI.

    Returns:
        List of (document_index, relevance_score) tuples sorted by score.
    """
    if not query.strip():
        raise ValueError("Query cannot be empty")
    if not documents:
        return []

    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{FIREWORKS_BASE_URL}/rerank",
                headers={
                    "Authorization": f"Bearer {settings.fireworks_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": RERANK_MODEL,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k,
                },
            )
            response.raise_for_status()
            data = response.json()
            return [(item["index"], item["relevance_score"]) for item in data["results"]]
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Rerank API error {e.response.status_code}: {e.response.text}")
