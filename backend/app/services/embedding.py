"""Embedding service using Together AI SDK."""

from together import AsyncTogether

from app.config import settings


EMBEDDING_MODEL = "togethercomputer/m2-bert-80M-8k-retrieval"
RERANK_MODEL = "Salesforce/Llama-Rank-V1"
EMBEDDING_DIM = 768

_client: AsyncTogether | None = None


def get_client() -> AsyncTogether:
    """Get or create the AsyncTogether client."""
    global _client
    if _client is None:
        _client = AsyncTogether(api_key=settings.together_api_key)
    return _client


async def embed_text(text: str) -> list[float]:
    """Generate embedding for a single text."""
    client = get_client()
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    client = get_client()
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    # Sort by index to maintain order
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]


async def rerank(query: str, documents: list[str], top_k: int = 15) -> list[tuple[int, float]]:
    """Rerank documents using Together AI reranker."""
    client = get_client()
    response = await client.rerank.create(
        model=RERANK_MODEL,
        query=query,
        documents=documents,
        top_n=top_k,
    )
    return [(item.index, item.relevance_score) for item in response.results]


async def close_client() -> None:
    """Close the client connection (call on shutdown)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
