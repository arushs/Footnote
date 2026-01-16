"""Diff-based folder synchronization with Google Drive.

Efficiently detects and queues changed files for re-indexing.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from functools import partial

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import Chunk, File, Folder, IndexingJob

logger = logging.getLogger(__name__)

# Only sync if last sync was more than 1 hour ago
SYNC_INTERVAL = timedelta(hours=1)


async def sync_folder_if_needed(
    db: AsyncSession,
    folder: Folder,
    access_token: str,
    refresh_token: str,
) -> dict:
    """
    Check if folder needs sync and perform diff-based update.

    Performance: Runs blocking Google API calls in thread pool.

    Args:
        db: Database session
        folder: Folder to sync
        access_token: Google OAuth access token
        refresh_token: Google OAuth refresh token

    Returns:
        Dict with sync status and changes made
    """
    now = datetime.now(timezone.utc)

    # Check if sync is needed
    if folder.last_synced_at and (now - folder.last_synced_at) < SYNC_INTERVAL:
        return {"synced": False, "reason": "recent_sync"}

    try:
        # Build Drive service credentials
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        # Run blocking Google API in thread pool
        loop = asyncio.get_event_loop()
        service = await loop.run_in_executor(
            None,
            partial(build, "drive", "v3", credentials=credentials),
        )

        # Get current folder state from Drive
        current_files = await _list_drive_folder_async(loop, service, folder.google_folder_id)
        current_file_map = {f["id"]: f for f in current_files}

        # Get stored file state from database
        stored_files_result = await db.execute(
            select(File).where(File.folder_id == folder.id)
        )
        stored_files = {f.google_file_id: f for f in stored_files_result.scalars()}

        # Compute diff
        changes = {"added": [], "modified": [], "deleted": []}

        # Find new and modified files
        for drive_id, drive_file in current_file_map.items():
            if drive_id not in stored_files:
                changes["added"].append(drive_file)
            else:
                stored = stored_files[drive_id]
                drive_modified = datetime.fromisoformat(
                    drive_file["modifiedTime"].replace("Z", "+00:00")
                )
                if stored.modified_time and drive_modified > stored.modified_time:
                    changes["modified"].append(drive_file)

        # Find deleted files
        for drive_id, stored_file in stored_files.items():
            if drive_id not in current_file_map:
                changes["deleted"].append(stored_file)

        # Apply changes
        await _apply_sync_changes(db, folder, changes)

        # Update sync timestamp
        folder.last_synced_at = now
        folder.files_total = len(current_files)
        await db.commit()

        logger.info(
            f"Synced folder {folder.id}: "
            f"+{len(changes['added'])} ~{len(changes['modified'])} -{len(changes['deleted'])}"
        )

        return {
            "synced": True,
            "added": len(changes["added"]),
            "modified": len(changes["modified"]),
            "deleted": len(changes["deleted"]),
        }

    except HttpError as e:
        if e.resp.status == 404:
            # Folder deleted on Drive
            logger.warning(f"Folder {folder.id} not found on Drive")
            folder.index_status = "error"
            await db.commit()
            return {"synced": False, "reason": "folder_not_found"}
        elif e.resp.status == 403:
            # Permission revoked
            logger.warning(f"Permission denied for folder {folder.id}")
            return {"synced": False, "reason": "permission_denied"}
        elif e.resp.status == 429:
            # Rate limited
            logger.warning(f"Rate limited while syncing folder {folder.id}")
            return {"synced": False, "reason": "rate_limited"}
        else:
            logger.error(f"Google API error syncing folder {folder.id}: {e}")
            return {"synced": False, "reason": "api_error", "error": str(e)}

    except Exception as e:
        logger.error(f"Error syncing folder {folder.id}: {e}")
        return {"synced": False, "reason": "error", "error": str(e)}


async def _list_drive_folder_async(loop, service, folder_id: str) -> list[dict]:
    """List all files in a Drive folder (with pagination) - async wrapper."""
    files = []
    page_token = None

    while True:
        # Run blocking call in thread pool
        response = await loop.run_in_executor(
            None,
            lambda pt=page_token: service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                pageSize=100,
                pageToken=pt,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                supportsAllDrives=True,
            )
            .execute(),
        )

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return files


async def _apply_sync_changes(db: AsyncSession, folder: Folder, changes: dict):
    """Apply diff changes to database and queue re-indexing."""

    # Delete removed files (cascade handles chunks via FK)
    for file in changes["deleted"]:
        await db.delete(file)

    # Queue new files for indexing
    for drive_file in changes["added"]:
        new_file = File(
            folder_id=folder.id,
            google_file_id=drive_file["id"],
            file_name=drive_file["name"],
            mime_type=drive_file["mimeType"],
            modified_time=datetime.fromisoformat(
                drive_file["modifiedTime"].replace("Z", "+00:00")
            ),
            index_status="pending",
        )
        db.add(new_file)
        await db.flush()  # Get the file ID

        job = IndexingJob(
            folder_id=folder.id,
            file_id=new_file.id,
            status="pending",
        )
        db.add(job)

    # Queue modified files for re-indexing
    for drive_file in changes["modified"]:
        file_result = await db.execute(
            select(File).where(
                File.folder_id == folder.id,
                File.google_file_id == drive_file["id"],
            )
        )
        file = file_result.scalar_one_or_none()
        if not file:
            continue

        # Delete old chunks (will be re-created during indexing)
        await db.execute(delete(Chunk).where(Chunk.file_id == file.id))

        # Update file record and queue re-indexing
        file.modified_time = datetime.fromisoformat(
            drive_file["modifiedTime"].replace("Z", "+00:00")
        )
        file.index_status = "pending"
        file.file_embedding = None
        file.file_preview = None
        file.search_vector = None

        # Check if job already exists for this file
        existing_job = await db.execute(
            select(IndexingJob).where(IndexingJob.file_id == file.id)
        )
        if not existing_job.scalar_one_or_none():
            job = IndexingJob(
                folder_id=folder.id,
                file_id=file.id,
                status="pending",
            )
            db.add(job)
