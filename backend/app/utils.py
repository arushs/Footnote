"""Shared utilities used across the application."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import text

from app.models import Session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def validate_uuid(value: str, name: str = "ID") -> uuid.UUID:
    """Validate and convert a string to UUID.

    Args:
        value: String to validate as UUID
        name: Human-readable name for error messages

    Returns:
        Validated UUID

    Raises:
        HTTPException: 400 if the string is not a valid UUID
    """
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {name}") from None


def format_vector(embedding: list[float]) -> str:
    """Format embedding list as PostgreSQL vector string."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def build_google_drive_url(google_file_id: str) -> str:
    """Build a Google Drive URL for a file."""
    return f"https://drive.google.com/file/d/{google_file_id}/view"


def format_location(location: dict, mime_type: str | None = None) -> str:
    """
    Format chunk location into a human-readable string.

    Args:
        location: Location dict with page, headings, or index
        mime_type: Optional mime type for context (used by chat routes)

    Returns:
        Human-readable location string
    """
    if not location:
        return "Document"
    if "page" in location:
        return f"Page {location['page']}"
    if "headings" in location and location["headings"]:
        return " > ".join(location["headings"])
    if "heading_path" in location and location["heading_path"]:
        return location["heading_path"]
    if "index" in location:
        return f"Section {location['index'] + 1}"
    return "Document"


async def get_user_session_for_folder(db: AsyncSession, folder_id: uuid.UUID) -> Session | None:
    """Get a valid user session for accessing files in a folder."""
    result = await db.execute(
        text("""
            SELECT s.id, s.user_id, s.access_token, s.refresh_token, s.expires_at
            FROM sessions s
            JOIN folders f ON f.user_id = s.user_id
            WHERE f.id = :folder_id
              AND s.expires_at > NOW()
            ORDER BY s.expires_at DESC
            LIMIT 1
        """),
        {"folder_id": str(folder_id)},
    )
    row = result.first()
    if row:
        return Session(
            id=row.id,
            user_id=row.user_id,
            access_token=row.access_token,
            refresh_token=row.refresh_token,
            expires_at=row.expires_at,
        )
    return None
