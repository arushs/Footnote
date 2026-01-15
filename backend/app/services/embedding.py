"""Embedding service using Together AI SDK."""

from together import AsyncTogether

from app.config import settings


EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM = 768
RERANK_MODEL = "Salesforce/Llama-Rank-V1"


def _get_client() -> AsyncTogether:
    """Create an async Together client."""
    return AsyncTogether(api_key=settings.together_api_key)


async def embed_text(text: str) -> list[float]:
    """Generate embedding for a single text."""
    client = _get_client()
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    client = _get_client()
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def rerank(query: str, documents: list[str], top_k: int = 15) -> list[tuple[int, float]]:
    """Rerank documents using Llama-Rank via Together AI."""
    client = _get_client()
    response = await client.rerank.create(
        model=RERANK_MODEL,
        query=query,
        documents=documents,
        top_n=top_k,
    )
    return [(item.index, item.relevance_score) for item in response.results]
