"""Diff-based folder synchronization with Google Drive.

Efficiently detects and queues changed files for re-indexing.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from functools import partial

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Chunk, File, Folder
from app.services.file.extraction import ExtractionService
from app.tasks.indexing import process_indexing_job

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
    now = datetime.now(UTC)

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
        stored_files_result = await db.execute(select(File).where(File.folder_id == folder.id))
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

        # Apply changes (pass user_id for Celery task dispatch)
        await _apply_sync_changes(db, folder, changes, str(folder.user_id))

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


async def _apply_sync_changes(db: AsyncSession, folder: Folder, changes: dict, user_id: str):
    """Apply diff changes to database and queue re-indexing via Celery."""
    extraction = ExtractionService()

    # Delete removed files (cascade handles chunks via FK)
    for file in changes["deleted"]:
        await db.delete(file)

    # Collect new files to dispatch after commit
    new_file_records = []

    # Queue new files for indexing (skip unsupported types like images)
    for drive_file in changes["added"]:
        mime_type = drive_file["mimeType"]
        if not extraction.is_supported(mime_type):
            logger.debug(f"Skipping unsupported file type: {drive_file['name']} ({mime_type})")
            continue
        new_file = File(
            folder_id=folder.id,
            google_file_id=drive_file["id"],
            file_name=drive_file["name"],
            mime_type=drive_file["mimeType"],
            modified_time=datetime.fromisoformat(drive_file["modifiedTime"].replace("Z", "+00:00")),
            index_status="pending",
        )
        db.add(new_file)
        new_file_records.append(new_file)

    # Collect modified files to dispatch after commit
    modified_file_records = []

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

        # Update file record
        file.modified_time = datetime.fromisoformat(
            drive_file["modifiedTime"].replace("Z", "+00:00")
        )
        file.index_status = "pending"
        file.file_embedding = None
        file.file_preview = None
        file.search_vector = None

        modified_file_records.append(file)

    # Flush to get IDs for new files
    await db.flush()

    # Dispatch Celery tasks for new and modified files
    dispatch_errors = []
    for file_record in new_file_records + modified_file_records:
        try:
            process_indexing_job.delay(
                file_id=str(file_record.id),
                folder_id=str(folder.id),
                user_id=user_id,
            )
        except Exception as e:
            dispatch_errors.append((file_record.id, str(e)))

    if dispatch_errors:
        logger.error(f"Failed to dispatch {len(dispatch_errors)} sync tasks: {dispatch_errors}")
