"""Chat endpoint with RAG-based answer generation and citations."""

import json
import re
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Cookie
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.services.anthropic import get_client
from app.models.db_models import (
    Folder,
    File,
    Chunk,
    Conversation,
    Message,
    Session as DbSession,
)
from app.routes.auth import get_current_session
from app.services.embedding import embed_query, rerank

router = APIRouter()

# Number of chunks to retrieve and rerank
INITIAL_RETRIEVAL_K = 50
RERANK_TOP_K = 15
CONTEXT_TOP_K = 8


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
    title: str | None
    preview: str
    created_at: str
    updated_at: str


class ConversationCreate(BaseModel):
    folder_id: str


class ConversationUpdate(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    id: str
    folder_id: str
    title: str | None
    created_at: str
    updated_at: str


def format_location(location: dict, mime_type: str) -> str:
    """Format chunk location into a human-readable string."""
    if "page" in location:
        return f"Page {location['page']}"
    if "headings" in location and location["headings"]:
        return " > ".join(location["headings"])
    if "index" in location:
        return f"Section {location['index'] + 1}"
    return "Document"


def build_google_drive_url(google_file_id: str) -> str:
    """Build a Google Drive URL for a file."""
    return f"https://drive.google.com/file/d/{google_file_id}/view"


async def retrieve_chunks(
    db: AsyncSession,
    folder_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = INITIAL_RETRIEVAL_K,
) -> list[tuple[Chunk, File, float]]:
    """Retrieve chunks using pgvector cosine similarity search."""
    # Convert embedding to PostgreSQL array format
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Query using pgvector's cosine distance operator (<=>)
    query = text("""
        SELECT
            c.id,
            c.file_id,
            c.chunk_text,
            c.location,
            c.chunk_index,
            f.file_name,
            f.google_file_id,
            f.mime_type,
            (c.chunk_embedding <=> CAST(:embedding AS vector)) as distance
        FROM chunks c
        JOIN files f ON c.file_id = f.id
        WHERE f.folder_id = :folder_id
          AND c.chunk_embedding IS NOT NULL
        ORDER BY c.chunk_embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(
        query,
        {
            "embedding": embedding_str,
            "folder_id": folder_id,
            "top_k": top_k,
        },
    )
    rows = result.fetchall()

    chunks_with_files = []
    for row in rows:
        chunk = Chunk(
            id=row.id,
            file_id=row.file_id,
            chunk_text=row.chunk_text,
            location=row.location,
            chunk_index=row.chunk_index,
        )
        file = File(
            id=row.file_id,
            file_name=row.file_name,
            google_file_id=row.google_file_id,
            mime_type=row.mime_type,
        )
        # Convert distance to similarity (1 - distance for cosine)
        similarity = 1 - row.distance
        chunks_with_files.append((chunk, file, similarity))

    return chunks_with_files


async def rerank_chunks(
    query: str,
    chunks_with_files: list[tuple[Chunk, File, float]],
    top_k: int = RERANK_TOP_K,
) -> list[tuple[Chunk, File, float]]:
    """Rerank chunks using the reranking model."""
    if not chunks_with_files:
        return []

    documents = [chunk.chunk_text for chunk, _, _ in chunks_with_files]
    reranked_indices = await rerank(query, documents, top_k=top_k)

    reranked_chunks = []
    for idx, score in reranked_indices:
        chunk, file, _ = chunks_with_files[idx]
        reranked_chunks.append((chunk, file, score))

    return reranked_chunks


def build_context(chunks_with_files: list[tuple[Chunk, File, float]]) -> str:
    """Build context string from chunks for the LLM."""
    context_parts = []
    for i, (chunk, file, _) in enumerate(chunks_with_files):
        location = format_location(chunk.location, file.mime_type)
        context_parts.append(
            f"[{i + 1}] From '{file.file_name}' ({location}):\n{chunk.chunk_text}"
        )
    return "\n\n---\n\n".join(context_parts)


def build_system_prompt(context: str) -> str:
    """Build the system prompt with context for the LLM."""
    return f"""You are a helpful assistant that answers questions based on the provided documents.
Your task is to provide accurate, well-structured answers using ONLY the information from the provided context.

IMPORTANT INSTRUCTIONS:
1. Base your answers ONLY on the provided context. Do not make up information.
2. When you use information from the context, cite the source using [N] notation where N is the source number.
3. If the context doesn't contain enough information to fully answer the question, say so clearly.
4. Be concise but thorough. Structure your response for clarity.
5. Use multiple citations when information comes from multiple sources.

CONTEXT:
{context}

Remember: Always cite your sources using [1], [2], etc. matching the source numbers above."""


def extract_citation_numbers(text: str) -> set[int]:
    """Extract citation numbers from the response text."""
    # Match [1], [2], [3], etc.
    pattern = r"\[(\d+)\]"
    matches = re.findall(pattern, text)
    return {int(m) for m in matches}


async def generate_streaming_response(
    db: AsyncSession,
    folder_id: uuid.UUID,
    conversation: Conversation,
    user_message: str,
    chunks_with_files: list[tuple[Chunk, File, float]],
    searched_files: list[str],
) -> AsyncGenerator[str, None]:
    """Generate streaming response from Claude with citations."""
    # Build context from top chunks for generation
    top_chunks = chunks_with_files[:CONTEXT_TOP_K]
    context = build_context(top_chunks)
    system_prompt = build_system_prompt(context)

    # Get conversation history for context
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

    # Store user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    await db.flush()

    # Stream response from Claude using the shared client
    client = get_client()
    full_response = ""

    try:
        async with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield f'data: {json.dumps({"token": text})}\n\n'
    except Exception as e:
        yield f'data: {json.dumps({"error": str(e)})}\n\n'
        return

    # Extract citations from the response
    citation_numbers = extract_citation_numbers(full_response)
    citations = {}

    for num in citation_numbers:
        if 1 <= num <= len(top_chunks):
            chunk, file, _ = top_chunks[num - 1]
            location = format_location(chunk.location, file.mime_type)
            excerpt = chunk.chunk_text[:200] + "..." if len(chunk.chunk_text) > 200 else chunk.chunk_text

            citations[str(num)] = {
                "chunk_id": str(chunk.id),
                "file_name": file.file_name,
                "location": location,
                "excerpt": excerpt,
                "google_drive_url": build_google_drive_url(file.google_file_id),
            }

    # Store assistant message with citations
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=full_response,
        citations=citations,
    )
    db.add(assistant_msg)
    await db.flush()

    # Send final message with citations and metadata
    yield f'data: {json.dumps({"done": True, "citations": citations, "searched_files": searched_files, "conversation_id": str(conversation.id)})}\n\n'


@router.post("/folders/{folder_id}/chat")
async def chat(
    folder_id: str,
    request: ChatRequest,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a streaming response with citations."""
    # Validate folder ID
    try:
        folder_uuid = uuid.UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID")

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

    if folder.index_status != "ready":
        raise HTTPException(
            status_code=400,
            detail="Folder is still being indexed. Please wait.",
        )

    # Get or create conversation
    if request.conversation_id:
        try:
            conv_uuid = uuid.UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID")

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

    # Generate query embedding
    query_embedding = await embed_query(request.message)

    # Retrieve relevant chunks
    chunks_with_files = await retrieve_chunks(db, folder_uuid, query_embedding)

    # Get list of searched files (unique file names)
    searched_files = list({file.file_name for _, file, _ in chunks_with_files})

    # Rerank chunks
    if chunks_with_files:
        chunks_with_files = await rerank_chunks(request.message, chunks_with_files)

    # Generate streaming response
    return StreamingResponse(
        generate_streaming_response(
            db,
            folder_uuid,
            conversation,
            request.message,
            chunks_with_files,
            searched_files,
        ),
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
        raise HTTPException(status_code=400, detail="Invalid folder ID")

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

    # Get conversations with their first user message as preview
    result = await db.execute(
        select(Conversation)
        .where(Conversation.folder_id == folder_uuid)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.created_at.desc())
    )
    conversations = result.scalars().all()

    previews = []
    for conv in conversations:
        # Find first user message for preview
        user_messages = [m for m in conv.messages if m.role == "user"]
        if user_messages:
            first_msg = min(user_messages, key=lambda m: m.created_at)
            preview = first_msg.content[:100] + "..." if len(first_msg.content) > 100 else first_msg.content
        else:
            preview = "New conversation"

        previews.append(
            ConversationPreview(
                id=str(conv.id),
                title=conv.title,
                preview=preview,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
            )
        )

    return previews


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
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

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
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at)
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
    try:
        chunk_uuid = uuid.UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chunk ID")

    # Get chunk with file and folder info
    result = await db.execute(
        select(Chunk)
        .where(Chunk.id == chunk_uuid)
        .options(
            selectinload(Chunk.file).selectinload(File.folder)
        )
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
        "location": format_location(chunk.location, chunk.file.mime_type),
        "google_drive_url": build_google_drive_url(chunk.file.google_file_id),
        "context": [
            {
                "chunk_id": str(c.id),
                "text": c.chunk_text,
                "location": format_location(c.location, chunk.file.mime_type),
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
        raise HTTPException(status_code=400, detail="Invalid folder ID")

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
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

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
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

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
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

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
async def chat_in_conversation(
    conversation_id: str,
    request: ChatRequest,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to an existing conversation."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

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
    if folder.index_status != "ready":
        raise HTTPException(
            status_code=400,
            detail="Folder is still being indexed. Please wait.",
        )

    # Generate query embedding
    query_embedding = await embed_query(request.message)

    # Retrieve relevant chunks from the folder
    chunks_with_files = await retrieve_chunks(db, folder.id, query_embedding)

    # Get list of searched files (unique file names)
    searched_files = list({file.file_name for _, file, _ in chunks_with_files})

    # Rerank chunks
    if chunks_with_files:
        chunks_with_files = await rerank_chunks(request.message, chunks_with_files)

    # Generate streaming response
    return StreamingResponse(
        generate_streaming_response(
            db,
            folder.id,
            conversation,
            request.message,
            chunks_with_files,
            searched_files,
        ),
        media_type="text/event-stream",
    )
