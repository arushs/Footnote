"""Chat routes for conversational RAG."""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.retrieval import retrieve_and_rerank, format_context_for_llm

import anthropic

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class CitationData(BaseModel):
    chunk_id: str
    file_name: str
    location: str
    excerpt: str
    google_drive_url: str


class ChatMessage(BaseModel):
    text: str
    citations: dict[str, CitationData]


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    searched_files: list[str]


class ConversationPreview(BaseModel):
    id: str
    preview: str
    created_at: str


SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided document context.

When answering:
1. Base your answers ONLY on the provided context from the user's documents
2. When citing information, use the format [Source N] to reference the source
3. If the context doesn't contain enough information to answer, say so honestly
4. Be concise but thorough in your responses
5. If multiple sources contain relevant information, synthesize them into a coherent answer

The context below contains excerpts from the user's Google Drive documents, with source references you should use when citing."""


@router.post("/folders/{folder_id}/chat")
async def chat(folder_id: str, request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Send a message and get a streaming response with citations."""
    folder_uuid = uuid.UUID(folder_id)

    # Verify folder exists
    result = await db.execute(
        text("SELECT id, index_status FROM folders WHERE id = :folder_id"),
        {"folder_id": folder_id},
    )
    folder = result.first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Get or create conversation
    if request.conversation_id:
        conv_id = uuid.UUID(request.conversation_id)
        result = await db.execute(
            text("SELECT id FROM conversations WHERE id = :conv_id AND folder_id = :folder_id"),
            {"conv_id": str(conv_id), "folder_id": folder_id},
        )
        if not result.first():
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv_id = uuid.uuid4()
        await db.execute(
            text("INSERT INTO conversations (id, folder_id) VALUES (:id, :folder_id)"),
            {"id": str(conv_id), "folder_id": folder_id},
        )

    # Retrieve relevant chunks
    retrieved_chunks = await retrieve_and_rerank(
        db=db,
        query=request.message,
        folder_id=folder_uuid,
        initial_top_k=30,
        final_top_k=10,
    )

    # Build context for LLM
    context = format_context_for_llm(retrieved_chunks)

    # Get list of searched files
    searched_files = list(set(chunk.file_name for chunk in retrieved_chunks))

    # Build citations map
    citations: dict[str, CitationData] = {}
    for i, chunk in enumerate(retrieved_chunks, 1):
        source_key = f"Source {i}"
        location_str = _format_location_for_citation(chunk.location)
        drive_url = f"https://drive.google.com/file/d/{chunk.google_file_id}/view"

        citations[source_key] = CitationData(
            chunk_id=str(chunk.chunk_id),
            file_name=chunk.file_name,
            location=location_str,
            excerpt=chunk.chunk_text[:300] + "..." if len(chunk.chunk_text) > 300 else chunk.chunk_text,
            google_drive_url=drive_url,
        )

    # Save user message
    await db.execute(
        text("""
            INSERT INTO messages (id, conversation_id, role, content)
            VALUES (:id, :conv_id, 'user', :content)
        """),
        {"id": str(uuid.uuid4()), "conv_id": str(conv_id), "content": request.message},
    )

    async def generate():
        """Stream the response from Anthropic."""
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Build message with context
        user_message = f"""Context from documents:
{context}

---

User question: {request.message}"""

        full_response = ""

        try:
            async with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    full_response += text_chunk
                    yield f'data: {json.dumps({"token": text_chunk})}\n\n'

            # Save assistant message with citations
            await db.execute(
                text("""
                    INSERT INTO messages (id, conversation_id, role, content, citations)
                    VALUES (:id, :conv_id, 'assistant', :content, :citations)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "conv_id": str(conv_id),
                    "content": full_response,
                    "citations": json.dumps({k: v.model_dump() for k, v in citations.items()}),
                },
            )
            await db.commit()

            # Send final message with metadata
            final_data = {
                "done": True,
                "citations": {k: v.model_dump() for k, v in citations.items()},
                "searched_files": searched_files,
                "conversation_id": str(conv_id),
            }
            yield f'data: {json.dumps(final_data)}\n\n'

        except Exception as e:
            yield f'data: {json.dumps({"error": str(e)})}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/folders/{folder_id}/conversations")
async def list_conversations(folder_id: str, db: AsyncSession = Depends(get_db)) -> list[ConversationPreview]:
    """List all conversations for a folder."""
    result = await db.execute(
        text("""
            SELECT
                c.id,
                c.created_at,
                (
                    SELECT content
                    FROM messages m
                    WHERE m.conversation_id = c.id AND m.role = 'user'
                    ORDER BY m.created_at ASC
                    LIMIT 1
                ) as first_message
            FROM conversations c
            WHERE c.folder_id = :folder_id
            ORDER BY c.created_at DESC
        """),
        {"folder_id": folder_id},
    )

    rows = result.fetchall()
    return [
        ConversationPreview(
            id=str(row.id),
            preview=row.first_message[:100] + "..." if row.first_message and len(row.first_message) > 100 else (row.first_message or "New conversation"),
            created_at=row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
        )
        for row in rows
    ]


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: dict | None
    created_at: str


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str, db: AsyncSession = Depends(get_db)) -> list[MessageResponse]:
    """Get all messages in a conversation."""
    result = await db.execute(
        text("""
            SELECT id, role, content, citations, created_at
            FROM messages
            WHERE conversation_id = :conv_id
            ORDER BY created_at ASC
        """),
        {"conv_id": conversation_id},
    )

    rows = result.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return [
        MessageResponse(
            id=str(row.id),
            role=row.role,
            content=row.content,
            citations=row.citations,
            created_at=row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
        )
        for row in rows
    ]


class ChunkContextResponse(BaseModel):
    chunk_id: str
    file_name: str
    chunk_text: str
    location: dict
    surrounding_chunks: list[dict]


@router.get("/chunks/{chunk_id}/context")
async def get_chunk_context(chunk_id: str, db: AsyncSession = Depends(get_db)) -> ChunkContextResponse:
    """Get surrounding context for a chunk (for citations)."""
    # Get the target chunk
    result = await db.execute(
        text("""
            SELECT c.id, c.file_id, c.chunk_text, c.location, c.chunk_index, f.file_name
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            WHERE c.id = :chunk_id
        """),
        {"chunk_id": chunk_id},
    )
    chunk = result.first()

    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    # Get surrounding chunks (previous and next)
    result = await db.execute(
        text("""
            SELECT id, chunk_text, location, chunk_index
            FROM chunks
            WHERE file_id = :file_id
              AND chunk_index BETWEEN :start_idx AND :end_idx
              AND id != :chunk_id
            ORDER BY chunk_index
        """),
        {
            "file_id": str(chunk.file_id),
            "start_idx": max(0, chunk.chunk_index - 2),
            "end_idx": chunk.chunk_index + 2,
            "chunk_id": chunk_id,
        },
    )

    surrounding = [
        {
            "id": str(row.id),
            "chunk_text": row.chunk_text,
            "location": row.location,
            "chunk_index": row.chunk_index,
        }
        for row in result.fetchall()
    ]

    return ChunkContextResponse(
        chunk_id=str(chunk.id),
        file_name=chunk.file_name,
        chunk_text=chunk.chunk_text,
        location=chunk.location,
        surrounding_chunks=surrounding,
    )


def _format_location_for_citation(location: dict) -> str:
    """Format location dict as a citation-friendly string."""
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
        return ", ".join(parts)
    return "Document"
