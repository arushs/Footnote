"""Standard single-shot RAG using hybrid search.

This is the default chat mode - fast and predictable.
Combines semantic similarity with keyword matching via RRF fusion.
"""

import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Conversation, Message
from app.services.anthropic import get_client
from app.services.hybrid_search import hybrid_retrieve_and_rerank
from app.services.posthog import LLMTimer, track_llm_generation, track_span
from app.utils import build_google_drive_url, format_location

logger = logging.getLogger(__name__)

CONTEXT_TOP_K = 8

STANDARD_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided documents.

## Response Format
- Use **markdown headers** (## or ###) to organize longer answers into sections
- Use **bullet points** or numbered lists when presenting multiple items
- Keep paragraphs short and scannable
- Bold key terms or important findings

## Citations
- Cite sources **inline** using [N] notation immediately after the claim or fact
- Place citations right after the relevant statement, not at the end of paragraphs
- Example: "Revenue grew 15% [1] while costs decreased [2]."
- Combine citations like [1][2] when a point draws from multiple sources

## Guidelines
- Base answers ONLY on the provided context - don't make up information
- If the context doesn't fully answer the question, say so clearly
- Be concise and direct"""


@dataclass
class Citation:
    """Citation metadata for a source."""

    chunk_id: str
    file_name: str
    location: str
    excerpt: str
    google_drive_url: str


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
    user_id: uuid.UUID,
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
    # Generate trace ID for this RAG request
    trace_id = str(uuid.uuid4())

    # 1. Hybrid search with reranking
    with LLMTimer() as retrieval_timer:
        chunks = await hybrid_retrieve_and_rerank(
            db=db,
            query=user_message,
            folder_id=folder_id,
            user_id=user_id,
            initial_top_k=30,
            final_top_k=15,
        )

    # Track retrieval span
    retrieval_scores = [
        {
            "file": c.file_name,
            "score": round(c.similarity_score, 3),
            "rerank": round(c.rerank_score, 3) if c.rerank_score else None,
        }
        for c in chunks[:5]  # Top 5 for brevity
    ]
    track_span(
        distinct_id=str(user_id),
        trace_id=trace_id,
        span_name="hybrid_search_and_rerank",
        input_state={"query": user_message, "initial_top_k": 30, "final_top_k": 15},
        output_state={"candidates": len(chunks), "top_scores": retrieval_scores},
        latency_ms=retrieval_timer.elapsed_ms,
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
    input_tokens = 0
    output_tokens = 0

    try:
        with LLMTimer() as timer:
            async with client.messages.stream(
                model=settings.claude_model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    yield f"data: {json.dumps({'token': text})}\n\n"

                # Get final message for token usage
                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens

    except Exception as e:
        logger.error(f"Error streaming response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return

    # 6. Extract citations from the response
    citation_numbers = extract_citation_numbers(full_response)
    citations = {}

    for num in citation_numbers:
        if 1 <= num <= len(top_chunks):
            chunk = top_chunks[num - 1]
            location = format_location(chunk.location)
            excerpt = (
                chunk.chunk_text[:200] + "..." if len(chunk.chunk_text) > 200 else chunk.chunk_text
            )

            citations[str(num)] = {
                "chunk_id": str(chunk.chunk_id),
                "file_name": chunk.file_name,
                "location": location,
                "excerpt": excerpt,
                "google_drive_url": build_google_drive_url(chunk.google_file_id),
            }

    # Track LLM generation in PostHog (after citations extracted)
    track_llm_generation(
        distinct_id=str(user_id),
        model=settings.claude_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=timer.elapsed_ms,
        trace_id=trace_id,
        properties={
            "mode": "standard_rag",
            "conversation_id": str(conversation.id),
            "context_chunks": len(top_chunks),
            "context_chars": len(context),
            "citations_used": len(citations),
            "files_searched": len(searched_files),
        },
    )

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
    yield f"data: {json.dumps({'done': True, 'citations': citations, 'searched_files': searched_files, 'conversation_id': str(conversation.id)})}\n\n"
