"""RAG (Retrieval-Augmented Generation) service."""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import Chunk, File
from app.services import embedding
from app.services import anthropic as anthropic_service


RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context documents.

Instructions:
- Answer based ONLY on the provided context
- When you use information from a specific document, cite it using [doc_N] format where N is the document number
- If the context doesn't contain relevant information, say so clearly
- Be concise but thorough

Context documents will be provided in the following format:
[doc_1] filename.ext: content...
[doc_2] filename.ext: content...
"""


@dataclass
class Citation:
    """A citation reference."""

    chunk_id: str
    file_name: str
    location: dict
    excerpt: str
    google_drive_url: str


async def retrieve_chunks(
    db: AsyncSession,
    folder_id: UUID,
    query: str,
    initial_k: int = 50,
    rerank_k: int = 10,
) -> list[Chunk]:
    """Retrieve and rerank relevant chunks for a query."""
    # Step 1: Get query embedding
    query_embedding = await embedding.embed_text(query)

    # Step 2: Vector similarity search using pgvector
    stmt = (
        select(Chunk)
        .join(File)
        .where(File.folder_id == folder_id)
        .where(Chunk.chunk_embedding.isnot(None))
        .order_by(Chunk.chunk_embedding.cosine_distance(query_embedding))
        .limit(initial_k)
        .options(selectinload(Chunk.file))
    )
    result = await db.execute(stmt)
    initial_chunks = list(result.scalars().all())

    if not initial_chunks:
        return []

    # Step 3: Rerank with cross-encoder
    documents = [chunk.chunk_text for chunk in initial_chunks]
    reranked = await embedding.rerank(query, documents, top_k=rerank_k)

    # Step 4: Return reranked chunks
    return [initial_chunks[idx] for idx, _ in reranked]


def _build_context(chunks: list[Chunk]) -> str:
    """Build context string from chunks."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        file_name = chunk.file.file_name if chunk.file else "unknown"
        context_parts.append(f"[doc_{i}] {file_name}: {chunk.chunk_text}")
    return "\n\n".join(context_parts)


def _build_citations(chunks: list[Chunk]) -> dict[str, dict]:
    """Build citations dictionary from chunks."""
    citations = {}
    for i, chunk in enumerate(chunks, 1):
        file = chunk.file
        citation = Citation(
            chunk_id=str(chunk.id),
            file_name=file.file_name if file else "unknown",
            location=chunk.location,
            excerpt=chunk.chunk_text[:200] + "..." if len(chunk.chunk_text) > 200 else chunk.chunk_text,
            google_drive_url=f"https://drive.google.com/file/d/{file.google_file_id}/view" if file else "",
        )
        citations[f"doc_{i}"] = {
            "chunk_id": citation.chunk_id,
            "file_name": citation.file_name,
            "location": json.dumps(citation.location),
            "excerpt": citation.excerpt,
            "google_drive_url": citation.google_drive_url,
        }
    return citations


async def answer_stream(
    db: AsyncSession,
    folder_id: UUID,
    query: str,
    conversation_history: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """
    Answer a query with streaming response.

    Yields:
        {"token": "..."} for each text chunk
        {"done": true, "citations": {...}} at the end
    """
    # Retrieve relevant chunks
    chunks = await retrieve_chunks(db, folder_id, query)

    if not chunks:
        yield {"token": "I couldn't find any relevant information in the documents to answer your question."}
        yield {"done": True, "citations": {}}
        return

    # Build context and messages
    context = _build_context(chunks)

    messages = conversation_history.copy() if conversation_history else []
    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {query}",
    })

    # Stream response from Anthropic
    async for text in anthropic_service.generate_stream(
        messages=messages,
        system_prompt=RAG_SYSTEM_PROMPT,
        max_tokens=2048,
        temperature=0.3,
    ):
        yield {"token": text}

    # Build and yield citations at the end
    citations = _build_citations(chunks)
    yield {"done": True, "citations": citations}
