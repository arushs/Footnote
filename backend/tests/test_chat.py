"""Integration tests for chat endpoints."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.db_models import Chunk, Conversation, File, Folder, Message
from app.routes.chat import (
    build_context,
    build_google_drive_url,
    extract_citation_numbers,
    format_location,
)


class TestChatEndpoint:
    """Tests for the main chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_requires_authentication(
        self, client: AsyncClient, test_folder: Folder
    ):
        """Test that chat endpoint requires authentication."""
        response = await client.post(
            f"/api/folders/{test_folder.id}/chat",
            json={"message": "What is machine learning?"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_returns_404_for_nonexistent_folder(
        self, auth_client: AsyncClient
    ):
        """Test that chat returns 404 for nonexistent folder."""
        response = await auth_client.post(
            f"/api/folders/{uuid.uuid4()}/chat",
            json={"message": "Hello"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_returns_400_for_invalid_folder_id(
        self, auth_client: AsyncClient
    ):
        """Test that chat returns 400 for invalid folder ID."""
        response = await auth_client.post(
            "/api/folders/not-a-uuid/chat",
            json={"message": "Hello"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_returns_400_for_indexing_folder(
        self, auth_client: AsyncClient, indexing_folder: Folder
    ):
        """Test that chat returns 400 when folder is still indexing."""
        response = await auth_client.post(
            f"/api/folders/{indexing_folder.id}/chat",
            json={"message": "Hello"},
        )

        assert response.status_code == 400
        assert "still being indexed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_chat_creates_new_conversation(
        self,
        auth_client: AsyncClient,
        db_session,
        test_folder: Folder,
        test_file: File,
        test_chunks: list[Chunk],
        mock_embedding_service,
        mock_anthropic,
    ):
        """Test that chat creates a new conversation and returns streaming response."""
        with patch("app.routes.chat.embed_text", mock_embedding_service["embed_text"]), \
             patch("app.routes.chat.rerank", mock_embedding_service["rerank"]), \
             patch("app.routes.chat.get_client", return_value=mock_anthropic):

            response = await auth_client.post(
                f"/api/folders/{test_folder.id}/chat",
                json={"message": "What is in this document?"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE response
        content = response.text
        events = [line for line in content.split("\n\n") if line.startswith("data:")]
        assert len(events) > 0

        # Last event should contain done flag
        last_event = json.loads(events[-1].replace("data: ", ""))
        assert last_event.get("done") is True
        assert "conversation_id" in last_event

    @pytest.mark.asyncio
    async def test_chat_continues_existing_conversation(
        self,
        auth_client: AsyncClient,
        db_session,
        test_folder: Folder,
        test_file: File,
        test_chunks: list[Chunk],
        test_conversation: Conversation,
        mock_embedding_service,
        mock_anthropic,
    ):
        """Test that chat can continue an existing conversation."""
        with patch("app.routes.chat.embed_text", mock_embedding_service["embed_text"]), \
             patch("app.routes.chat.rerank", mock_embedding_service["rerank"]), \
             patch("app.routes.chat.get_client", return_value=mock_anthropic):

            response = await auth_client.post(
                f"/api/folders/{test_folder.id}/chat",
                json={
                    "message": "Tell me more",
                    "conversation_id": str(test_conversation.id),
                },
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_returns_404_for_invalid_conversation(
        self,
        auth_client: AsyncClient,
        test_folder: Folder,
    ):
        """Test that chat returns 404 for invalid conversation ID."""
        response = await auth_client.post(
            f"/api/folders/{test_folder.id}/chat",
            json={
                "message": "Hello",
                "conversation_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404


class TestListConversations:
    """Tests for listing conversations."""

    @pytest.mark.asyncio
    async def test_list_conversations_returns_folder_conversations(
        self,
        auth_client: AsyncClient,
        test_folder: Folder,
        test_conversation: Conversation,
        test_messages: list[Message],
    ):
        """Test that list conversations returns all conversations for a folder."""
        response = await auth_client.get(
            f"/api/folders/{test_folder.id}/conversations"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(test_conversation.id)
        assert "What is machine learning?" in data[0]["preview"]

    @pytest.mark.asyncio
    async def test_list_conversations_empty_folder(
        self, auth_client: AsyncClient, test_folder: Folder
    ):
        """Test that list conversations returns empty for folder with no conversations."""
        response = await auth_client.get(
            f"/api/folders/{test_folder.id}/conversations"
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_conversations_not_found_for_nonexistent_folder(
        self, auth_client: AsyncClient
    ):
        """Test that list conversations returns 404 for nonexistent folder."""
        response = await auth_client.get(
            f"/api/folders/{uuid.uuid4()}/conversations"
        )

        assert response.status_code == 404


class TestGetConversationMessages:
    """Tests for getting conversation messages."""

    @pytest.mark.asyncio
    async def test_get_messages_returns_all_messages(
        self,
        auth_client: AsyncClient,
        test_conversation: Conversation,
        test_messages: list[Message],
    ):
        """Test that get messages returns all messages in conversation."""
        response = await auth_client.get(
            f"/api/conversations/{test_conversation.id}/messages"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"
        assert "citations" in data[1]

    @pytest.mark.asyncio
    async def test_get_messages_not_found(self, auth_client: AsyncClient):
        """Test that get messages returns 404 for nonexistent conversation."""
        response = await auth_client.get(
            f"/api/conversations/{uuid.uuid4()}/messages"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_messages_forbidden_for_other_user(
        self, client: AsyncClient, db_session, test_conversation: Conversation
    ):
        """Test that user cannot access another user's conversation."""
        from app.models.db_models import Session, User
        from datetime import datetime, timedelta, timezone

        other_user = User(
            id=uuid.uuid4(),
            google_id="msg-other-google-id",
            email="msg-other@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_session = Session(
            id=uuid.uuid4(),
            user_id=other_user.id,
            access_token="other-token",
            refresh_token="other-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(other_session)
        await db_session.flush()

        client.cookies.set("session_id", str(other_session.id))
        response = await client.get(
            f"/api/conversations/{test_conversation.id}/messages"
        )

        assert response.status_code == 403


class TestGetChunkContext:
    """Tests for getting chunk context."""

    @pytest.mark.asyncio
    async def test_get_chunk_context_returns_surrounding_chunks(
        self,
        auth_client: AsyncClient,
        test_file: File,
        test_chunks: list[Chunk],
    ):
        """Test that get chunk context returns the chunk and surrounding chunks."""
        # Get the middle chunk
        middle_chunk = test_chunks[1]

        response = await auth_client.get(f"/api/chunks/{middle_chunk.id}/context")

        assert response.status_code == 200
        data = response.json()
        assert data["chunk_id"] == str(middle_chunk.id)
        assert data["file_name"] == test_file.file_name
        assert "context" in data
        # Should include chunks before and after
        assert len(data["context"]) >= 1

    @pytest.mark.asyncio
    async def test_get_chunk_context_not_found(self, auth_client: AsyncClient):
        """Test that get chunk context returns 404 for nonexistent chunk."""
        response = await auth_client.get(f"/api/chunks/{uuid.uuid4()}/context")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_chunk_context_forbidden_for_other_user(
        self, client: AsyncClient, db_session, test_chunks: list[Chunk]
    ):
        """Test that user cannot access another user's chunk."""
        from app.models.db_models import Session, User
        from datetime import datetime, timedelta, timezone

        other_user = User(
            id=uuid.uuid4(),
            google_id="chunk-other-google-id",
            email="chunk-other@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_session = Session(
            id=uuid.uuid4(),
            user_id=other_user.id,
            access_token="other-token",
            refresh_token="other-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(other_session)
        await db_session.flush()

        client.cookies.set("session_id", str(other_session.id))
        response = await client.get(f"/api/chunks/{test_chunks[0].id}/context")

        assert response.status_code == 403


class TestHelperFunctions:
    """Tests for chat helper functions."""

    def test_format_location_with_page(self):
        """Test format_location with page number."""
        location = {"page": 5}
        result = format_location(location, "application/pdf")
        assert result == "Page 5"

    def test_format_location_with_headings(self):
        """Test format_location with headings."""
        location = {"headings": ["Chapter 1", "Section 1.1"]}
        result = format_location(location, "application/vnd.google-apps.document")
        assert result == "Chapter 1 > Section 1.1"

    def test_format_location_with_index(self):
        """Test format_location with index."""
        location = {"index": 2}
        result = format_location(location, "application/pdf")
        assert result == "Section 3"

    def test_format_location_fallback(self):
        """Test format_location fallback."""
        location = {}
        result = format_location(location, "application/pdf")
        assert result == "Document"

    def test_build_google_drive_url(self):
        """Test Google Drive URL construction."""
        file_id = "abc123"
        url = build_google_drive_url(file_id)
        assert url == "https://drive.google.com/file/d/abc123/view"

    def test_extract_citation_numbers(self):
        """Test citation number extraction from text."""
        text = "This is content [1] with multiple [2] citations [1] and [3]."
        numbers = extract_citation_numbers(text)
        assert numbers == {1, 2, 3}

    def test_extract_citation_numbers_empty(self):
        """Test citation extraction with no citations."""
        text = "This is content without any citations."
        numbers = extract_citation_numbers(text)
        assert numbers == set()

    def test_build_context(self):
        """Test context building from chunks."""
        from app.models.db_models import Chunk, File

        chunks_with_files = [
            (
                Chunk(
                    id=uuid.uuid4(),
                    file_id=uuid.uuid4(),
                    chunk_text="First chunk content",
                    location={"page": 1},
                    chunk_index=0,
                ),
                File(
                    id=uuid.uuid4(),
                    folder_id=uuid.uuid4(),
                    google_file_id="file1",
                    file_name="Document1.pdf",
                    mime_type="application/pdf",
                    index_status="indexed",
                ),
                0.95,
            ),
            (
                Chunk(
                    id=uuid.uuid4(),
                    file_id=uuid.uuid4(),
                    chunk_text="Second chunk content",
                    location={"headings": ["Intro"]},
                    chunk_index=0,
                ),
                File(
                    id=uuid.uuid4(),
                    folder_id=uuid.uuid4(),
                    google_file_id="file2",
                    file_name="Document2.pdf",
                    mime_type="application/vnd.google-apps.document",
                    index_status="indexed",
                ),
                0.85,
            ),
        ]

        context = build_context(chunks_with_files)

        assert "[1] From 'Document1.pdf' (Page 1):" in context
        assert "First chunk content" in context
        assert "[2] From 'Document2.pdf' (Intro):" in context
        assert "Second chunk content" in context
        assert "---" in context  # Separator between chunks
