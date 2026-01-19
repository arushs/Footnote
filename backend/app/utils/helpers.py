"""Shared utilities used across the application."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models import Session


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
    # Import here to avoid circular import (models imports utils)
    from app.models import Folder, Session

    stmt = (
        select(Session)
        .join(Folder, Folder.user_id == Session.user_id)
        .where(Folder.id == folder_id)
        .where(Session.expires_at > datetime.now(UTC))
        .order_by(Session.expires_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
