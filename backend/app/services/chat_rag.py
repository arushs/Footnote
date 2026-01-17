"""Standard single-shot RAG using hybrid search.

This is the default chat mode - fast and predictable.
Combines semantic similarity with keyword matching via RRF fusion.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import Conversation, Message
from app.services.anthropic import get_client
from app.services.hybrid_search import hybrid_retrieve_and_rerank

logger = logging.getLogger(__name__)

CONTEXT_TOP_K = 8

STANDARD_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided documents.
Your task is to provide accurate, well-structured answers using ONLY the information from the provided context.

IMPORTANT INSTRUCTIONS:
1. Base your answers ONLY on the provided context. Do not make up information.
2. When you use information from the context, cite the source using [N] notation where N is the source number.
3. If the context doesn't contain enough information to fully answer the question, say so clearly.
4. Be concise but thorough. Structure your response for clarity.
5. Use multiple citations when information comes from multiple sources.

Remember: Always cite your sources using [1], [2], etc. matching the source numbers above."""


@dataclass
class Citation:
    """Citation metadata for a source."""

    chunk_id: str
    file_name: str
    location: str
    excerpt: str
    google_drive_url: str


def format_location(location: dict) -> str:
    """Format chunk location into a human-readable string."""
    if not location:
        return "Document"
    if "page" in location:
        return f"Page {location['page']}"
    if "headings" in location and location["headings"]:
        return " > ".join(location["headings"])
    if "heading_path" in location and location["heading_path"]:
        return location["heading_path"]
    if "index" in location:
        return f"Section {location['index'] + 1}"
    return "Document"


def build_google_drive_url(google_file_id: str) -> str:
    """Build a Google Drive URL for a file."""
    return f"https://drive.google.com/file/d/{google_file_id}/view"


def build_context(chunks: list) -> str:
    """Build context string from chunks for the LLM."""
    context_parts = []
    for i, chunk in enumerate(chunks):
        location = format_location(chunk.location)
        context_parts.append(
            f"[{i + 1}] From '{chunk.file_name}' ({location}):\n{chunk.chunk_text}"
        )
    return "\n\n---\n\n".join(context_parts)


def extract_citation_numbers(text: str) -> set[int]:
    """Extract citation numbers from the response text."""
    pattern = r"\[(\d+)\]"
    matches = re.findall(pattern, text)
    return {int(m) for m in matches}


async def standard_rag(
    db: AsyncSession,
    folder_id: uuid.UUID,
    conversation: Conversation,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Standard single-shot RAG: hybrid search once, generate response.

    This is the default mode - fast, predictable, handles ~90% of queries well.

    Args:
        db: Database session
        folder_id: Folder to search within
        conversation: Conversation object for message storage
        user_message: User's query

    Yields:
        SSE-formatted chunks for streaming response
    """
    # 1. Hybrid search with reranking
    chunks = await hybrid_retrieve_and_rerank(
        db=db,
        query=user_message,
        folder_id=folder_id,
        initial_top_k=30,
        final_top_k=15,
    )

    # Get list of searched files (unique file names)
    searched_files = list({chunk.file_name for chunk in chunks})

    # 2. Build context from top chunks
    top_chunks = chunks[:CONTEXT_TOP_K]
    context = build_context(top_chunks)
    system_prompt = f"{STANDARD_SYSTEM_PROMPT}\n\nCONTEXT:\n{context}"

    # 3. Get conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    history_messages = history_result.scalars().all()

    # Build messages list
    messages = []
    for msg in history_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    # 4. Store user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    await db.commit()  # Explicit commit for streaming response

    # 5. Stream response from Claude
    client = get_client()
    full_response = ""

    try:
        async with client.messages.stream(
            model=settings.claude_model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield f'data: {json.dumps({"token": text})}\n\n'
    except Exception as e:
        logger.error(f"Error streaming response: {e}")
        yield f'data: {json.dumps({"error": str(e)})}\n\n'
        return

    # 6. Extract citations from the response
    citation_numbers = extract_citation_numbers(full_response)
    citations = {}

    for num in citation_numbers:
        if 1 <= num <= len(top_chunks):
            chunk = top_chunks[num - 1]
            location = format_location(chunk.location)
            excerpt = (
                chunk.chunk_text[:200] + "..."
                if len(chunk.chunk_text) > 200
                else chunk.chunk_text
            )

            citations[str(num)] = {
                "chunk_id": str(chunk.chunk_id),
                "file_name": chunk.file_name,
                "location": location,
                "excerpt": excerpt,
                "google_drive_url": build_google_drive_url(chunk.google_file_id),
            }

    # 7. Store assistant message with citations
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=full_response,
        citations=citations,
    )
    db.add(assistant_msg)
    await db.commit()  # Explicit commit for streaming response

    # 8. Send final message with metadata
    yield f'data: {json.dumps({"done": True, "citations": citations, "searched_files": searched_files, "conversation_id": str(conversation.id)})}\n\n'
