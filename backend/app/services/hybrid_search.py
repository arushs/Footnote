"""Hybrid search service combining vector similarity, keyword matching, and recency."""

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file.embedding import embed_query, rerank

logger = logging.getLogger(__name__)

# Scoring weights (should sum to 1.0)
VECTOR_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.2
RECENCY_WEIGHT = 0.2

# Recency decay half-life in days (score halves every N days)
RECENCY_HALF_LIFE_DAYS = 30


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


@dataclass
class HybridSearchResult:
    """Result from hybrid search with combined scoring."""

    chunk_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    google_file_id: str
    chunk_text: str
    location: dict
    file_updated_at: datetime | None
    vector_score: float
    keyword_score: float
    recency_score: float
    weighted_score: float
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


def calculate_recency_score(updated_at: datetime | None, half_life_days: float = RECENCY_HALF_LIFE_DAYS) -> float:
    """Calculate recency score using exponential decay.

    Score of 1.0 for now, 0.5 after half_life_days, 0.25 after 2*half_life_days, etc.

    Args:
        updated_at: When the file was last updated
        half_life_days: Number of days for score to halve

    Returns:
        Recency score between 0 and 1
    """
    if updated_at is None:
        return 0.5  # Default score for unknown dates

    now = datetime.now(UTC)
    # Ensure updated_at is timezone-aware
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)

    age_days = (now - updated_at).total_seconds() / 86400  # Convert to days

    if age_days < 0:
        return 1.0  # Future dates get max score

    # Exponential decay: score = 0.5^(age/half_life) = e^(-ln(2) * age / half_life)
    decay_rate = math.log(2) / half_life_days
    return math.exp(-decay_rate * age_days)


def calculate_weighted_score(
    vector_score: float,
    keyword_score: float,
    recency_score: float,
    vector_weight: float = VECTOR_WEIGHT,
    keyword_weight: float = KEYWORD_WEIGHT,
    recency_weight: float = RECENCY_WEIGHT,
) -> float:
    """Calculate combined weighted score.

    All input scores should be normalized to 0-1 range.

    Args:
        vector_score: Cosine similarity score (0-1)
        keyword_score: Normalized keyword match score (0-1)
        recency_score: Recency decay score (0-1)
        vector_weight: Weight for vector similarity
        keyword_weight: Weight for keyword matching
        recency_weight: Weight for recency

    Returns:
        Combined weighted score
    """
    return (
        vector_weight * vector_score +
        keyword_weight * keyword_score +
        recency_weight * recency_score
    )


async def keyword_search(
    db: AsyncSession,
    query: str,
    folder_id: uuid.UUID,
    top_k: int = 30,
) -> list[tuple[uuid.UUID, float]]:
    """
    Perform full-text keyword search using tsvector.

    Args:
        db: Database session
        query: User's search query
        folder_id: Folder to search within
        top_k: Number of results to return

    Returns:
        List of (chunk_id, normalized_score) tuples ordered by relevance
    """
    # Convert query to OR-based format for more forgiving matching
    or_query = build_or_query(query)
    logger.info(f"[HYBRID] Keyword query: '{or_query[:50]}...'")

    result = await db.execute(
        text("""
            SELECT
                c.id as chunk_id,
                ts_rank(c.search_vector, websearch_to_tsquery('english', :query)) as score
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            WHERE f.folder_id = :folder_id
              AND c.search_vector @@ websearch_to_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :top_k
        """),
        {
            "query": or_query,
            "folder_id": str(folder_id),
            "top_k": top_k,
        },
    )

    rows = result.fetchall()
    if not rows:
        return []

    # Normalize scores to 0-1 range using max score
    max_score = max(row.score for row in rows) if rows else 1.0
    if max_score == 0:
        max_score = 1.0

    return [(row.chunk_id, row.score / max_score) for row in rows]


async def vector_search_with_scores(
    db: AsyncSession,
    query_embedding: list[float],
    folder_id: uuid.UUID,
    top_k: int = 30,
) -> list[tuple[uuid.UUID, float, dict]]:
    """
    Perform vector similarity search returning similarity scores.

    Args:
        db: Database session
        query_embedding: Embedding vector for the query
        folder_id: Folder to search within
        top_k: Number of results to return

    Returns:
        List of (chunk_id, similarity_score, chunk_data) tuples ordered by similarity
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
                f.updated_at as file_updated_at,
                1 - (c.chunk_embedding <=> CAST(:query_embedding AS vector)) as similarity
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
            max(0.0, row.similarity),  # Clamp to non-negative
            {
                "file_id": row.file_id,
                "chunk_text": row.chunk_text,
                "location": row.location,
                "file_name": row.file_name,
                "google_file_id": row.google_file_id,
                "file_updated_at": row.file_updated_at,
            },
        )
        for row in result.fetchall()
    ]


async def hybrid_search(
    db: AsyncSession,
    query: str,
    folder_id: uuid.UUID,
    top_k: int = 30,
) -> list[HybridSearchResult]:
    """
    Perform hybrid search combining vector similarity, keyword matching, and recency.

    Uses weighted scoring: score = w1*vector + w2*keyword + w3*recency

    Args:
        db: Database session
        query: User's search query
        folder_id: Folder to search within
        top_k: Number of results to return

    Returns:
        List of hybrid search results ordered by combined weighted score
    """
    logger.info(
        f"[HYBRID] Starting hybrid search for query: '{query[:50]}...' in folder {folder_id}"
    )
    query_embedding = await embed_query(query)
    logger.info(f"[HYBRID] Got embedding (length: {len(query_embedding)})")

    vector_results = await vector_search_with_scores(db, query_embedding, folder_id, top_k)
    logger.info(f"[HYBRID] Vector search returned {len(vector_results)} results")

    keyword_results = await keyword_search(db, query, folder_id, top_k)
    logger.info(f"[HYBRID] Keyword search returned {len(keyword_results)} results")

    # Build lookup maps
    keyword_scores: dict[uuid.UUID, float] = {chunk_id: score for chunk_id, score in keyword_results}

    # Build combined results from vector search
    chunk_data: dict[uuid.UUID, dict] = {}
    vector_scores: dict[uuid.UUID, float] = {}

    for chunk_id, similarity, data in vector_results:
        vector_scores[chunk_id] = similarity
        chunk_data[chunk_id] = data

    # For keyword-only results, fetch their data
    keyword_only_ids = set(keyword_scores.keys()) - set(vector_scores.keys())
    if keyword_only_ids:
        result = await db.execute(
            text("""
                SELECT
                    c.id as chunk_id,
                    c.file_id,
                    c.chunk_text,
                    c.location,
                    f.file_name,
                    f.google_file_id,
                    f.updated_at as file_updated_at
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
                "file_updated_at": row.file_updated_at,
            }

    # Combine all chunk IDs
    all_chunk_ids = set(vector_scores.keys()) | set(keyword_scores.keys())

    # Calculate weighted scores and build results
    results = []
    for chunk_id in all_chunk_ids:
        v_score = vector_scores.get(chunk_id, 0.0)
        k_score = keyword_scores.get(chunk_id, 0.0)

        data = chunk_data.get(chunk_id, {})
        file_updated_at = data.get("file_updated_at")
        r_score = calculate_recency_score(file_updated_at)

        weighted = calculate_weighted_score(v_score, k_score, r_score)

        results.append(
            HybridSearchResult(
                chunk_id=chunk_id,
                file_id=data.get("file_id"),
                file_name=data.get("file_name", "Unknown"),
                google_file_id=data.get("google_file_id", ""),
                chunk_text=data.get("chunk_text", ""),
                location=data.get("location", {}),
                file_updated_at=file_updated_at,
                vector_score=v_score,
                keyword_score=k_score,
                recency_score=r_score,
                weighted_score=weighted,
            )
        )

    # Sort by weighted score descending
    results.sort(key=lambda x: x.weighted_score, reverse=True)
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

    Combines vector + keyword + recency via weighted scoring, then reranks the top results.

    Args:
        db: Database session
        query: User's search query
        folder_id: Folder to search within
        initial_top_k: Number of candidates from hybrid search
        final_top_k: Final number of results after reranking

    Returns:
        List of retrieved chunks ordered by rerank score
    """
    # Stage 1: Hybrid search with weighted scoring
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
            similarity_score=c.weighted_score,
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
