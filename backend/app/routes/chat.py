"""Chat endpoint with RAG-based answer generation and citations."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import get_db
from app.enums import FolderStatus
from app.middleware.rate_limit import limiter
from app.models import Chunk, Conversation, File, Folder, Message
from app.models import Session as DbSession
from app.routes.auth import get_current_session
from app.services.chat import agentic_rag, standard_rag
from app.utils import build_google_drive_url, format_location, validate_uuid

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    agent_mode: bool = False  # Enable agent mode for iterative search
    max_iterations: int = 10  # Max tool-use iterations for agent mode

    @field_validator("message")
    @classmethod
    def validate_message_length(cls, v: str) -> str:
        """Enforce maximum message length to prevent resource exhaustion."""
        if len(v) > settings.max_chat_message_length:
            raise ValueError(
                f"Message exceeds maximum length of {settings.max_chat_message_length:,} characters"
            )
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v


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
    title: str | None
    preview: str
    created_at: str
    updated_at: str


class ConversationCreate(BaseModel):
    folder_id: str


class ConversationUpdate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title_length(cls, v: str) -> str:
        """Enforce maximum title length."""
        if len(v) > settings.max_conversation_title_length:
            raise ValueError(
                f"Title exceeds maximum length of {settings.max_conversation_title_length} characters"
            )
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


class ConversationResponse(BaseModel):
    id: str
    folder_id: str
    title: str | None
    created_at: str
    updated_at: str


@router.post("/folders/{folder_id}/chat")
@limiter.limit(f"{settings.rate_limit_chat_per_minute}/minute")
async def chat(
    request: Request,
    folder_id: str,
    chat_request: ChatRequest,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a streaming response with citations."""
    # Set user_id on request state for rate limiter
    request.state.user_id = str(session.user_id)
    # Validate folder ID
    try:
        folder_uuid = uuid.UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID") from None

    # Verify folder exists and belongs to user
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_uuid,
            Folder.user_id == session.user_id,
        )
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if folder.index_status != FolderStatus.READY:
        raise HTTPException(
            status_code=400,
            detail="Folder is still being indexed. Please wait.",
        )

    # Get or create conversation
    if chat_request.conversation_id:
        try:
            conv_uuid = uuid.UUID(chat_request.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID") from None

        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conv_uuid,
                Conversation.folder_id == folder_uuid,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(folder_id=folder_uuid)
        db.add(conversation)
        await db.flush()

    # Route to appropriate mode based on agent_mode flag
    logger.info(
        f"[CHAT] Chat request - agent_mode: {chat_request.agent_mode}, max_iterations: {chat_request.max_iterations}, message: {chat_request.message[:50]}..."
    )
    if chat_request.agent_mode:
        # Agent mode: iterative search with tools (slower, more thorough)
        logger.info(f"[CHAT] Using AGENT mode (max_iterations: {chat_request.max_iterations})")
        rag_generator = agentic_rag(
            db=db,
            folder_id=folder_uuid,
            user_id=session.user_id,
            conversation=conversation,
            user_message=chat_request.message,
            folder_name=folder.folder_name,
            files_indexed=folder.files_indexed,
            files_total=folder.files_total,
            max_iterations=chat_request.max_iterations,
        )
    else:
        # Standard mode: single-shot hybrid RAG (default, fast)
        logger.info("[CHAT] Using STANDARD mode")
        rag_generator = standard_rag(
            db=db,
            folder_id=folder_uuid,
            user_id=session.user_id,
            conversation=conversation,
            user_message=chat_request.message,
        )

    return StreamingResponse(
        rag_generator,
        media_type="text/event-stream",
    )


@router.get("/folders/{folder_id}/conversations")
async def list_conversations(
    folder_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationPreview]:
    """List all conversations for a folder."""
    try:
        folder_uuid = uuid.UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID") from None

    # Verify folder belongs to user
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_uuid,
            Folder.user_id == session.user_id,
        )
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Efficient query: fetch conversations with only first user message preview
    # Uses DISTINCT ON to get only the first user message per conversation
    result = await db.execute(
        text("""
            SELECT
                c.id,
                c.title,
                c.created_at,
                c.updated_at,
                COALESCE(
                    (
                        SELECT SUBSTRING(m.content, 1, 100)
                        FROM messages m
                        WHERE m.conversation_id = c.id
                          AND m.role = 'user'
                        ORDER BY m.created_at ASC
                        LIMIT 1
                    ),
                    'New conversation'
                ) as preview
            FROM conversations c
            WHERE c.folder_id = :folder_id
            ORDER BY c.created_at DESC
        """),
        {"folder_id": str(folder_uuid)},
    )
    rows = result.fetchall()

    return [
        ConversationPreview(
            id=str(row.id),
            title=row.title,
            preview=row.preview + "..." if len(row.preview) == 100 else row.preview,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )
        for row in rows
    ]


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a conversation."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID") from None

    # Get conversation and verify ownership through folder
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_uuid)
        .options(selectinload(Conversation.folder))
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.folder.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get messages
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_uuid).order_by(Message.created_at)
    )
    messages = result.scalars().all()

    return [
        {
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content,
            "citations": msg.citations or {},
            "created_at": msg.created_at.isoformat(),
        }
        for msg in messages
    ]


@router.get("/chunks/{chunk_id}/context")
async def get_chunk_context(
    chunk_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Get surrounding context for a chunk (for citations)."""
    chunk_uuid = validate_uuid(chunk_id, "chunk ID")

    # Get chunk with file and folder info
    result = await db.execute(
        select(Chunk)
        .where(Chunk.id == chunk_uuid)
        .options(selectinload(Chunk.file).selectinload(File.folder))
    )
    chunk = result.scalar_one_or_none()

    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    # Verify user has access to this chunk's folder
    if chunk.file.folder.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get surrounding chunks for context
    result = await db.execute(
        select(Chunk)
        .where(
            Chunk.file_id == chunk.file_id,
            Chunk.chunk_index >= chunk.chunk_index - 1,
            Chunk.chunk_index <= chunk.chunk_index + 1,
        )
        .order_by(Chunk.chunk_index)
    )
    surrounding_chunks = result.scalars().all()

    return {
        "chunk_id": str(chunk.id),
        "file_name": chunk.file.file_name,
        "location": format_location(chunk.location),
        "google_drive_url": build_google_drive_url(chunk.file.google_file_id),
        "context": [
            {
                "chunk_id": str(c.id),
                "text": c.chunk_text,
                "location": format_location(c.location),
                "is_target": c.id == chunk.id,
            }
            for c in surrounding_chunks
        ],
    }


# Conversation-centric routes


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation for a folder."""
    try:
        folder_uuid = uuid.UUID(request.folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID") from None

    # Verify folder exists and belongs to user
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_uuid,
            Folder.user_id == session.user_id,
        )
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    conversation = Conversation(folder_id=folder_uuid)
    db.add(conversation)
    await db.flush()

    return ConversationResponse(
        id=str(conversation.id),
        folder_id=str(conversation.folder_id),
        title=conversation.title,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation by ID."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID") from None

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_uuid)
        .options(selectinload(Conversation.folder))
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.folder.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ConversationResponse(
        id=str(conversation.id),
        folder_id=str(conversation.folder_id),
        title=conversation.title,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdate,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Update a conversation's title."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID") from None

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_uuid)
        .options(selectinload(Conversation.folder))
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.folder.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    conversation.title = request.title
    await db.flush()

    return ConversationResponse(
        id=str(conversation.id),
        folder_id=str(conversation.folder_id),
        title=conversation.title,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID") from None

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_uuid)
        .options(selectinload(Conversation.folder))
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.folder.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await db.delete(conversation)
    return {"message": "Conversation deleted successfully"}


@router.post("/conversations/{conversation_id}/chat")
@limiter.limit(f"{settings.rate_limit_chat_per_minute}/minute")
async def chat_in_conversation(
    request: Request,
    conversation_id: str,
    chat_request: ChatRequest,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to an existing conversation."""
    # Set user_id on request state for rate limiter
    request.state.user_id = str(session.user_id)
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID") from None

    # Get conversation with folder
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_uuid)
        .options(selectinload(Conversation.folder))
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.folder.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    folder = conversation.folder
    if folder.index_status != FolderStatus.READY:
        raise HTTPException(
            status_code=400,
            detail="Folder is still being indexed. Please wait.",
        )

    # Route to appropriate mode based on agent_mode flag
    logger.info(
        f"[CHAT] Conversation chat request - agent_mode: {chat_request.agent_mode}, max_iterations: {chat_request.max_iterations}, message: {chat_request.message[:50]}..."
    )
    if chat_request.agent_mode:
        # Agent mode: iterative search with tools (slower, more thorough)
        logger.info(
            f"[CHAT] Using AGENT mode (conversation, max_iterations: {chat_request.max_iterations})"
        )
        rag_generator = agentic_rag(
            db=db,
            folder_id=folder.id,
            user_id=session.user_id,
            conversation=conversation,
            user_message=chat_request.message,
            folder_name=folder.folder_name,
            files_indexed=folder.files_indexed,
            files_total=folder.files_total,
            max_iterations=chat_request.max_iterations,
        )
    else:
        # Standard mode: single-shot hybrid RAG (default, fast)
        logger.info("[CHAT] Using STANDARD mode (conversation)")
        rag_generator = standard_rag(
            db=db,
            folder_id=folder.id,
            user_id=session.user_id,
            conversation=conversation,
            user_message=chat_request.message,
        )

    return StreamingResponse(
        rag_generator,
        media_type="text/event-stream",
    )
