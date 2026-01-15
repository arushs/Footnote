"""Integration tests for authentication routes."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.db_models import Session, User


class TestGoogleLogin:
    """Tests for Google OAuth login redirect."""

    @pytest.mark.asyncio
    async def test_google_login_redirects_to_oauth(self, client: AsyncClient):
        """Test that /google redirects to Google OAuth consent screen."""
        response = await client.get("/api/auth/google", follow_redirects=False)

        assert response.status_code == 307  # RedirectResponse
        location = response.headers["location"]
        assert "accounts.google.com/o/oauth2/v2/auth" in location
        assert "client_id=test-client-id" in location
        assert "response_type=code" in location
        assert "access_type=offline" in location


class TestGoogleCallback:
    """Tests for Google OAuth callback handling."""

    @pytest.mark.asyncio
    async def test_callback_creates_new_user_and_session(
        self, client: AsyncClient, db_session
    ):
        """Test that callback creates a new user and session for new Google users."""
        with patch("httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = MagicMock()
            MockHttpxClient.return_value.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            MockHttpxClient.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock token exchange
            mock_token_response = MagicMock()
            mock_token_response.status_code = 200
            mock_token_response.json.return_value = {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            # Mock userinfo
            mock_userinfo_response = MagicMock()
            mock_userinfo_response.status_code = 200
            mock_userinfo_response.json.return_value = {
                "id": "new-google-user-123",
                "email": "newuser@example.com",
            }

            mock_client_instance.post = AsyncMock(return_value=mock_token_response)
            mock_client_instance.get = AsyncMock(return_value=mock_userinfo_response)

            response = await client.get(
                "/api/auth/google/callback?code=test-auth-code",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "session_id" in response.cookies

    @pytest.mark.asyncio
    async def test_callback_fails_with_invalid_code(self, client: AsyncClient):
        """Test that callback fails when token exchange fails."""
        with patch("httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = MagicMock()
            MockHttpxClient.return_value.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            MockHttpxClient.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock failed token exchange
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_client_instance.post = AsyncMock(return_value=mock_response)

            response = await client.get(
                "/api/auth/google/callback?code=invalid-code"
            )

            assert response.status_code == 400
            assert "Failed to exchange code" in response.json()["detail"]


class TestLogout:
    """Tests for logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_clears_session_cookie(self, auth_client: AsyncClient):
        """Test that logout clears the session cookie."""
        response = await auth_client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_deletes_session_from_database(
        self, auth_client: AsyncClient, db_session, test_session: Session
    ):
        """Test that logout deletes the session from the database."""
        response = await auth_client.post("/api/auth/logout")

        assert response.status_code == 200

        # Verify session is deleted
        from sqlalchemy import select

        result = await db_session.execute(
            select(Session).where(Session.id == test_session.id)
        )
        session = result.scalar_one_or_none()
        assert session is None

    @pytest.mark.asyncio
    async def test_logout_without_session_succeeds(self, client: AsyncClient):
        """Test that logout works even without a session cookie."""
        response = await client.post("/api/auth/logout")

        assert response.status_code == 200


class TestGetCurrentUser:
    """Tests for getting current authenticated user."""

    @pytest.mark.asyncio
    async def test_get_current_user_returns_user_info(
        self, auth_client: AsyncClient, test_user: User
    ):
        """Test that authenticated user can get their info."""
        response = await auth_client.get("/api/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["google_id"] == test_user.google_id

    @pytest.mark.asyncio
    async def test_get_current_user_fails_without_session(self, client: AsyncClient):
        """Test that unauthenticated request fails."""
        response = await client.get("/api/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    @pytest.mark.asyncio
    async def test_get_current_user_fails_with_invalid_session(
        self, client: AsyncClient
    ):
        """Test that invalid session ID fails."""
        client.cookies.set("session_id", "not-a-valid-uuid")
        response = await client.get("/api/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid session"

    @pytest.mark.asyncio
    async def test_get_current_user_fails_with_nonexistent_session(
        self, client: AsyncClient
    ):
        """Test that nonexistent session ID fails."""
        client.cookies.set("session_id", str(uuid.uuid4()))
        response = await client.get("/api/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "Session not found"

    @pytest.mark.asyncio
    async def test_get_current_user_refreshes_expired_token(
        self, client: AsyncClient, expired_session: Session, test_user: User
    ):
        """Test that expired session triggers token refresh."""
        with patch("httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = MagicMock()
            MockHttpxClient.return_value.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            MockHttpxClient.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock successful token refresh
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "refreshed-access-token",
                "expires_in": 3600,
            }
            mock_client_instance.post = AsyncMock(return_value=mock_response)

            client.cookies.set("session_id", str(expired_session.id))
            response = await client.get("/api/auth/me")

            assert response.status_code == 200
            assert response.json()["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_current_user_fails_when_refresh_fails(
        self, client: AsyncClient, expired_session: Session
    ):
        """Test that expired session with failed refresh returns 401."""
        with patch("httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = MagicMock()
            MockHttpxClient.return_value.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            MockHttpxClient.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock failed token refresh
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_client_instance.post = AsyncMock(return_value=mock_response)

            client.cookies.set("session_id", str(expired_session.id))
            response = await client.get("/api/auth/me")

            assert response.status_code == 401
            assert response.json()["detail"] == "Session expired"


class TestHealthCheck:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, client: AsyncClient):
        """Test that health check returns healthy status."""
        response = await client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
