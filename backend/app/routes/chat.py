"""Chat routes with RAG-based responses."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import rag

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


@router.post("/folders/{folder_id}/chat")
async def chat(
    folder_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a streaming RAG response."""
    try:
        folder_uuid = UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID")

    async def generate():
        try:
            async for chunk in rag.answer_stream(db, folder_uuid, request.message):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f'data: {{"error": "An error occurred: {str(e)}"}}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/folders/{folder_id}/conversations")
async def list_conversations(folder_id: str) -> list[ConversationPreview]:
    """List all conversations for a folder."""
    # TODO: Implement conversation listing
    return []


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """Get all messages in a conversation."""
    # TODO: Implement message retrieval
    raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/chunks/{chunk_id}/context")
async def get_chunk_context(chunk_id: str):
    """Get surrounding context for a chunk (for citations)."""
    # TODO: Implement chunk context retrieval
    raise HTTPException(status_code=404, detail="Chunk not found")
