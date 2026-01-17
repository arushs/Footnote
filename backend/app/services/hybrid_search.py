"""Hybrid search service combining vector similarity and keyword matching."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding import embed_query, rerank
from app.services.retrieval import RetrievedChunk, format_vector

logger = logging.getLogger(__name__)


# RRF fusion constant (higher values give more weight to top results)
RRF_K = 60


@dataclass
class HybridSearchResult:
    """Result from hybrid search with combined scoring."""

    chunk_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    google_file_id: str
    chunk_text: str
    location: dict
    vector_rank: int | None
    keyword_rank: int | None
    rrf_score: float
    rerank_score: float | None = None


def build_or_query(query: str) -> str:
    """Convert a query string to OR-based tsquery format.

    Splits on spaces and joins with OR for more forgiving matching.
    """
    # Split into words, filter out empty strings and common stop words
    words = [w.strip() for w in query.split() if w.strip() and len(w.strip()) > 2]
    if not words:
        return query
    # Join with OR for more forgiving matching
    return " OR ".join(words)


async def keyword_search(
    db: AsyncSession,
    query: str,
    folder_id: uuid.UUID,
    top_k: int = 30,
) -> list[tuple[uuid.UUID, int]]:
    """
    Perform full-text keyword search using tsvector.

    Args:
        db: Database session
        query: User's search query
        folder_id: Folder to search within
        top_k: Number of results to return

    Returns:
        List of (chunk_id, rank) tuples ordered by relevance
    """
    # Convert query to OR-based format for more forgiving matching
    or_query = build_or_query(query)
    logger.info(f"[HYBRID] Keyword query: '{or_query[:50]}...'")

    result = await db.execute(
        text("""
            SELECT
                c.id as chunk_id,
                ROW_NUMBER() OVER (ORDER BY ts_rank(c.search_vector, websearch_to_tsquery('english', :query)) DESC) as rank
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            WHERE f.folder_id = :folder_id
              AND c.search_vector @@ websearch_to_tsquery('english', :query)
            ORDER BY ts_rank(c.search_vector, websearch_to_tsquery('english', :query)) DESC
            LIMIT :top_k
        """),
        {
            "query": or_query,
            "folder_id": str(folder_id),
            "top_k": top_k,
        },
    )

    return [(row.chunk_id, row.rank) for row in result.fetchall()]


async def vector_search_with_rank(
    db: AsyncSession,
    query_embedding: list[float],
    folder_id: uuid.UUID,
    top_k: int = 30,
) -> list[tuple[uuid.UUID, int, dict]]:
    """
    Perform vector similarity search returning ranks.

    Args:
        db: Database session
        query_embedding: Embedding vector for the query
        folder_id: Folder to search within
        top_k: Number of results to return

    Returns:
        List of (chunk_id, rank, chunk_data) tuples ordered by similarity
    """
    result = await db.execute(
        text("""
            SELECT
                c.id as chunk_id,
                c.file_id,
                c.chunk_text,
                c.location,
                f.file_name,
                f.google_file_id,
                ROW_NUMBER() OVER (
                    ORDER BY c.chunk_embedding <=> CAST(:query_embedding AS vector)
                ) as rank
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            WHERE f.folder_id = :folder_id
              AND c.chunk_embedding IS NOT NULL
            ORDER BY c.chunk_embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
        """),
        {
            "query_embedding": format_vector(query_embedding),
            "folder_id": str(folder_id),
            "top_k": top_k,
        },
    )

    return [
        (
            row.chunk_id,
            row.rank,
            {
                "file_id": row.file_id,
                "chunk_text": row.chunk_text,
                "location": row.location,
                "file_name": row.file_name,
                "google_file_id": row.google_file_id,
            },
        )
        for row in result.fetchall()
    ]


def rrf_score(rank: int | None, k: int = RRF_K) -> float:
    """Calculate Reciprocal Rank Fusion score."""
    if rank is None:
        return 0.0
    return 1.0 / (k + rank)


async def hybrid_search(
    db: AsyncSession,
    query: str,
    folder_id: uuid.UUID,
    top_k: int = 30,
) -> list[HybridSearchResult]:
    """
    Perform hybrid search combining vector similarity and keyword matching.

    Uses Reciprocal Rank Fusion (RRF) to combine results from both methods.
    RRF score = 1/(k + rank_vector) + 1/(k + rank_keyword)

    Args:
        db: Database session
        query: User's search query
        folder_id: Folder to search within
        top_k: Number of results to return

    Returns:
        List of hybrid search results ordered by combined RRF score
    """
    # Run both searches in parallel conceptually (both are async)
    logger.info(f"[HYBRID] Starting hybrid search for query: '{query[:50]}...' in folder {folder_id}")
    query_embedding = await embed_query(query)
    logger.info(f"[HYBRID] Got embedding (length: {len(query_embedding)})")

    vector_results = await vector_search_with_rank(db, query_embedding, folder_id, top_k)
    logger.info(f"[HYBRID] Vector search returned {len(vector_results)} results")

    keyword_results = await keyword_search(db, query, folder_id, top_k)
    logger.info(f"[HYBRID] Keyword search returned {len(keyword_results)} results")

    # Build lookup maps
    keyword_ranks: dict[uuid.UUID, int] = {
        chunk_id: rank for chunk_id, rank in keyword_results
    }

    # Build combined results
    chunk_data: dict[uuid.UUID, dict] = {}
    vector_ranks: dict[uuid.UUID, int] = {}

    for chunk_id, rank, data in vector_results:
        vector_ranks[chunk_id] = rank
        chunk_data[chunk_id] = data

    # For keyword-only results, fetch their data
    keyword_only_ids = set(keyword_ranks.keys()) - set(vector_ranks.keys())
    if keyword_only_ids:
        result = await db.execute(
            text("""
                SELECT
                    c.id as chunk_id,
                    c.file_id,
                    c.chunk_text,
                    c.location,
                    f.file_name,
                    f.google_file_id
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE c.id = ANY(:chunk_ids)
            """),
            {"chunk_ids": list(keyword_only_ids)},
        )
        for row in result.fetchall():
            chunk_data[row.chunk_id] = {
                "file_id": row.file_id,
                "chunk_text": row.chunk_text,
                "location": row.location,
                "file_name": row.file_name,
                "google_file_id": row.google_file_id,
            }

    # Combine all chunk IDs
    all_chunk_ids = set(vector_ranks.keys()) | set(keyword_ranks.keys())

    # Calculate RRF scores and build results
    results = []
    for chunk_id in all_chunk_ids:
        v_rank = vector_ranks.get(chunk_id)
        k_rank = keyword_ranks.get(chunk_id)
        combined_score = rrf_score(v_rank) + rrf_score(k_rank)

        data = chunk_data.get(chunk_id, {})
        results.append(
            HybridSearchResult(
                chunk_id=chunk_id,
                file_id=data.get("file_id"),
                file_name=data.get("file_name", "Unknown"),
                google_file_id=data.get("google_file_id", ""),
                chunk_text=data.get("chunk_text", ""),
                location=data.get("location", {}),
                vector_rank=v_rank,
                keyword_rank=k_rank,
                rrf_score=combined_score,
            )
        )

    # Sort by RRF score descending
    results.sort(key=lambda x: x.rrf_score, reverse=True)
    return results[:top_k]


async def hybrid_retrieve_and_rerank(
    db: AsyncSession,
    query: str,
    folder_id: uuid.UUID,
    initial_top_k: int = 30,
    final_top_k: int = 10,
) -> list[RetrievedChunk]:
    """
    Hybrid retrieval with reranking.

    Combines vector + keyword search via RRF, then reranks the top results.

    Args:
        db: Database session
        query: User's search query
        folder_id: Folder to search within
        initial_top_k: Number of candidates from hybrid search
        final_top_k: Final number of results after reranking

    Returns:
        List of retrieved chunks ordered by rerank score
    """
    # Stage 1: Hybrid search
    candidates = await hybrid_search(db, query, folder_id, initial_top_k)

    if not candidates:
        return []

    # Convert to RetrievedChunk for compatibility
    chunks = [
        RetrievedChunk(
            chunk_id=c.chunk_id,
            file_id=c.file_id,
            file_name=c.file_name,
            google_file_id=c.google_file_id,
            chunk_text=c.chunk_text,
            location=c.location,
            similarity_score=c.rrf_score,
        )
        for c in candidates
    ]

    # If we have few candidates, skip reranking
    if len(chunks) <= final_top_k:
        return chunks

    # Stage 2: Rerank candidates
    documents = [chunk.chunk_text for chunk in chunks]
    reranked = await rerank(query, documents, top_k=final_top_k)

    # Map reranked indices back to chunks
    result = []
    for idx, score in reranked:
        chunk = chunks[idx]
        chunk.rerank_score = score
        result.append(chunk)

    return result
