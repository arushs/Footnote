"""Tests for the auth service."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.auth import refresh_access_token


@pytest.fixture
def mock_session():
    """Create a mock session object."""
    session = MagicMock()
    session.id = uuid.uuid4()
    session.refresh_token = "valid-refresh-token"
    session.access_token = "old-access-token"
    session.expires_at = datetime.now(UTC) - timedelta(hours=1)  # Expired
    return session


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    return db


class TestRefreshAccessToken:
    """Tests for token refresh functionality."""

    @pytest.mark.asyncio
    async def test_returns_none_without_refresh_token(self, mock_db):
        """Should return None if session has no refresh token."""
        session = MagicMock()
        session.refresh_token = None

        result = await refresh_access_token(session, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_with_empty_refresh_token(self, mock_db):
        """Should return None if refresh token is empty string."""
        session = MagicMock()
        session.refresh_token = ""

        result = await refresh_access_token(session, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_successful_refresh(self, mock_session, mock_db):
        """Should update session with new tokens on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }

        with patch("app.services.auth.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await refresh_access_token(mock_session, mock_db)

        assert result is not None
        assert mock_session.access_token == "new-access-token"
        assert mock_session.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_failed_refresh_returns_none(self, mock_session, mock_db):
        """Should return None on refresh failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid refresh token"

        with patch("app.services.auth.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await refresh_access_token(mock_session, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_on_failure_flag(self, mock_session, mock_db):
        """Should delete session when delete_on_failure=True."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid refresh token"

        with patch("app.services.auth.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await refresh_access_token(mock_session, mock_db, delete_on_failure=True)

        mock_db.delete.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_no_delete_on_failure_by_default(self, mock_session, mock_db):
        """Should not delete session by default on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid refresh token"

        with patch("app.services.auth.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await refresh_access_token(mock_session, mock_db)

        mock_db.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_refresh_token_if_returned(self, mock_session, mock_db):
        """Should update refresh token if Google returns a new one."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }

        with patch("app.services.auth.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await refresh_access_token(mock_session, mock_db)

        assert result is not None
        assert mock_session.refresh_token == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_use_raw_sql_flag(self, mock_session, mock_db):
        """Should use raw SQL for updates when use_raw_sql=True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }

        with patch("app.services.auth.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await refresh_access_token(mock_session, mock_db, use_raw_sql=True)

        # Should have called execute (raw SQL) and commit
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()
