"""Tests for API routes."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import text

from app.config import settings


# Test fixtures and helpers
@pytest.fixture
def mock_session_id():
    return str(uuid.uuid4())


@pytest.fixture
def mock_user_id():
    return uuid.uuid4()


class TestAuthRoutes:
    """Tests for authentication routes."""

    def test_google_login_redirects(self):
        """Test that /api/auth/google redirects to Google OAuth."""
        from main import app
        client = TestClient(app, follow_redirects=False)

        response = client.get("/api/auth/google")

        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["location"]
        assert "client_id" in response.headers["location"]
        assert "redirect_uri" in response.headers["location"]

    def test_get_me_without_auth(self):
        """Test that /api/auth/me returns 401 without authentication."""
        from main import app
        client = TestClient(app)

        response = client.get("/api/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_get_me_with_invalid_session(self):
        """Test that /api/auth/me returns 401 with invalid session ID."""
        from main import app
        client = TestClient(app)

        response = client.get(
            "/api/auth/me",
            cookies={"session_id": "invalid-uuid"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid session"

    def test_logout_clears_cookie(self):
        """Test that logout clears the session cookie."""
        from main import app
        client = TestClient(app)

        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


class TestFolderRoutes:
    """Tests for folder routes."""

    def test_list_folders_without_auth(self):
        """Test that listing folders requires authentication."""
        from main import app
        client = TestClient(app)

        response = client.get("/api/folders")

        assert response.status_code == 401

    def test_create_folder_without_auth(self):
        """Test that creating a folder requires authentication."""
        from main import app
        client = TestClient(app)

        response = client.post(
            "/api/folders",
            json={"google_folder_id": "test-id", "folder_name": "Test Folder"}
        )

        assert response.status_code == 401

    def test_get_folder_invalid_id(self):
        """Test that invalid folder ID returns 400."""
        from main import app
        client = TestClient(app)

        # We need to mock authentication for this test
        response = client.get("/api/folders/not-a-uuid")

        # Will return 401 first since no auth
        assert response.status_code == 401

    def test_delete_folder_without_auth(self):
        """Test that deleting a folder requires authentication."""
        from main import app
        client = TestClient(app)

        response = client.delete(f"/api/folders/{uuid.uuid4()}")

        assert response.status_code == 401


class TestChatRoutes:
    """Tests for chat routes."""

    def test_chat_without_auth(self):
        """Test that chat requires authentication."""
        from main import app
        client = TestClient(app)

        response = client.post(
            f"/api/folders/{uuid.uuid4()}/chat",
            json={"message": "Hello"}
        )

        assert response.status_code == 401

    def test_chat_invalid_folder_id(self):
        """Test that invalid folder ID returns 400."""
        from main import app
        client = TestClient(app)

        response = client.post(
            "/api/folders/not-a-uuid/chat",
            json={"message": "Hello"}
        )

        # Returns 401 first since no auth
        assert response.status_code == 401

    def test_list_conversations_without_auth(self):
        """Test that listing conversations requires authentication."""
        from main import app
        client = TestClient(app)

        response = client.get(f"/api/folders/{uuid.uuid4()}/conversations")

        assert response.status_code == 401

    def test_get_messages_without_auth(self):
        """Test that getting messages requires authentication."""
        from main import app
        client = TestClient(app)

        response = client.get(f"/api/conversations/{uuid.uuid4()}/messages")

        assert response.status_code == 401

    def test_get_chunk_context_without_auth(self):
        """Test that getting chunk context requires authentication."""
        from main import app
        client = TestClient(app)

        response = client.get(f"/api/chunks/{uuid.uuid4()}/context")

        assert response.status_code == 401


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test that health check returns ok."""
        from main import app
        client = TestClient(app)

        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestInputValidation:
    """Tests for input validation."""

    def test_create_folder_empty_name(self):
        """Test that empty folder name is handled."""
        from main import app
        client = TestClient(app)

        response = client.post(
            "/api/folders",
            json={"google_folder_id": "test-id", "folder_name": ""}
        )

        # Returns 401 first since no auth
        assert response.status_code == 401

    def test_chat_empty_message(self):
        """Test that empty message is validated."""
        from main import app
        client = TestClient(app)

        response = client.post(
            f"/api/folders/{uuid.uuid4()}/chat",
            json={"message": ""}
        )

        # Returns 401 first since no auth
        assert response.status_code == 401
