"""Authentication services for token management."""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Session

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def refresh_access_token(
    session: Session,
    db: AsyncSession,
    *,
    delete_on_failure: bool = False,
) -> Session | None:
    """Refresh an expired access token using the refresh token.

    Args:
        session: The session with an expired access token
        db: Database session
        delete_on_failure: If True, delete the session if refresh fails

    Returns:
        Updated session with new tokens, or None if refresh failed
    """
    if not session.refresh_token:
        logger.warning(f"No refresh token for session {session.id}")
        return None

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": session.refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if token_response.status_code != 200:
            logger.warning(
                f"Failed to refresh token for session {session.id}: {token_response.text}"
            )
            if delete_on_failure:
                await db.delete(session)
            return None

        tokens = token_response.json()
        new_access_token = tokens["access_token"]
        new_expires_at = datetime.now(UTC) + timedelta(seconds=tokens.get("expires_in", 3600))
        new_refresh_token = tokens.get("refresh_token", session.refresh_token)

        # Update via setters (handles encryption automatically)
        session.access_token = new_access_token
        session.refresh_token = new_refresh_token
        session.expires_at = new_expires_at

        logger.info(f"Successfully refreshed token for session {session.id}")
        return session
