"""Embedding service using Together AI (Nomic-embed-text-v1.5)."""

import httpx

from app.config import settings


TOGETHER_API_URL = "https://api.together.xyz/v1/embeddings"
EMBEDDING_MODEL = "togethercomputer/m2-bert-80M-8k-retrieval"  # or nomic-embed-text-v1.5
EMBEDDING_DIM = 768


async def embed_text(text: str) -> list[float]:
    """Generate embedding for a single text."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOGETHER_API_URL,
            headers={"Authorization": f"Bearer {settings.together_api_key}"},
            json={
                "model": EMBEDDING_MODEL,
                "input": text,
            },
        )
        response.raise_for_status()
        data = response.json()

    return data["data"][0]["embedding"]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOGETHER_API_URL,
            headers={"Authorization": f"Bearer {settings.together_api_key}"},
            json={
                "model": EMBEDDING_MODEL,
                "input": texts,
            },
        )
        response.raise_for_status()
        data = response.json()

    return [item["embedding"] for item in data["data"]]


async def rerank(query: str, documents: list[str], top_k: int = 15) -> list[tuple[int, float]]:
    """Rerank documents using BGE reranker via Together AI."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.together.xyz/v1/rerank",
            headers={"Authorization": f"Bearer {settings.together_api_key}"},
            json={
                "model": "Salesforce/Llama-Rank-V1",
                "query": query,
                "documents": documents,
                "top_n": top_k,
                "return_documents": False,
            },
        )
        response.raise_for_status()
        data = response.json()

    return [(item["index"], item["relevance_score"]) for item in data["results"]]
