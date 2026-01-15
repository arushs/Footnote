from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
async def chat(folder_id: str, request: ChatRequest):
    """Send a message and get a streaming response."""
    # TODO: Implement retrieval and generation with streaming

    async def generate():
        yield 'data: {"token": "This"}\n\n'
        yield 'data: {"token": " is"}\n\n'
        yield 'data: {"token": " a"}\n\n'
        yield 'data: {"token": " placeholder"}\n\n'
        yield 'data: {"token": " response."}\n\n'
        yield 'data: {"done": true, "citations": {}}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")


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
