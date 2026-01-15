"""Retrieval service for vector search and reranking."""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding import embed_query, rerank


def format_vector(embedding: list[float]) -> str:
    """Format embedding list as PostgreSQL vector string."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


@dataclass
class RetrievedChunk:
    """A chunk retrieved from vector search."""

    chunk_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    google_file_id: str
    chunk_text: str
    location: dict
    similarity_score: float
    rerank_score: float | None = None


async def vector_search(
    db: AsyncSession,
    query_embedding: list[float],
    folder_id: uuid.UUID,
    top_k: int = 30,
) -> list[RetrievedChunk]:
    """
    Perform vector similarity search for chunks in a folder.

    Args:
        db: Database session
        query_embedding: Embedding vector for the query
        folder_id: Folder to search within
        top_k: Number of results to return

    Returns:
        List of retrieved chunks ordered by similarity
    """
    # Use cosine similarity via pgvector (<=> operator)
    result = await db.execute(
        text("""
            SELECT
                c.id as chunk_id,
                c.file_id,
                c.chunk_text,
                c.location,
                f.file_name,
                f.google_file_id,
                1 - (c.chunk_embedding <=> :query_embedding::vector) as similarity
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            WHERE f.folder_id = :folder_id
              AND c.chunk_embedding IS NOT NULL
            ORDER BY c.chunk_embedding <=> :query_embedding::vector
            LIMIT :top_k
        """),
        {
            "query_embedding": format_vector(query_embedding),
            "folder_id": str(folder_id),
            "top_k": top_k,
        },
    )

    rows = result.fetchall()
    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            file_id=row.file_id,
            file_name=row.file_name,
            google_file_id=row.google_file_id,
            chunk_text=row.chunk_text,
            location=row.location,
            similarity_score=row.similarity,
        )
        for row in rows
    ]


async def retrieve_and_rerank(
    db: AsyncSession,
    query: str,
    folder_id: uuid.UUID,
    initial_top_k: int = 30,
    final_top_k: int = 10,
) -> list[RetrievedChunk]:
    """
    Two-stage retrieval: vector search followed by reranking.

    Args:
        db: Database session
        query: User's search query
        folder_id: Folder to search within
        initial_top_k: Number of candidates for reranking
        final_top_k: Final number of results after reranking

    Returns:
        List of retrieved chunks ordered by rerank score
    """
    # Stage 1: Embed query and perform vector search
    query_embedding = await embed_query(query)
    candidates = await vector_search(db, query_embedding, folder_id, initial_top_k)

    if not candidates:
        return []

    # If we have few candidates, skip reranking
    if len(candidates) <= final_top_k:
        return candidates

    # Stage 2: Rerank candidates
    documents = [chunk.chunk_text for chunk in candidates]
    reranked = await rerank(query, documents, top_k=final_top_k)

    # Map reranked indices back to chunks
    result = []
    for idx, score in reranked:
        chunk = candidates[idx]
        chunk.rerank_score = score
        result.append(chunk)

    return result


def format_context_for_llm(chunks: list[RetrievedChunk]) -> str:
    """
    Format retrieved chunks as context for the LLM.

    Args:
        chunks: List of retrieved chunks

    Returns:
        Formatted context string with source markers
    """
    if not chunks:
        return ""

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        location_str = _format_location(chunk.location)
        context_parts.append(
            f"[Source {i}: {chunk.file_name}{location_str}]\n{chunk.chunk_text}"
        )

    return "\n\n---\n\n".join(context_parts)


def _format_location(location: dict) -> str:
    """Format location dict as a human-readable string."""
    parts = []

    if location.get("type") == "pdf":
        page = location.get("page")
        if page:
            parts.append(f"Page {page}")
    elif location.get("type") == "doc":
        heading_path = location.get("heading_path")
        if heading_path:
            parts.append(heading_path)

    if parts:
        return f" ({', '.join(parts)})"
    return ""
