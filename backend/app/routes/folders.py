import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import File, Folder
from app.models import Session as DbSession
from app.routes.auth import get_current_session
from app.services.drive import DriveService
from app.services.folder_sync import sync_folder_if_needed
from app.tasks.indexing import process_indexing_job

logger = logging.getLogger(__name__)

router = APIRouter()


class FolderCreate(BaseModel):
    google_folder_id: str
    folder_name: str


class FolderResponse(BaseModel):
    id: str
    google_folder_id: str
    folder_name: str
    index_status: str
    files_total: int
    files_indexed: int
    last_synced_at: str | None = None


class FolderStatus(BaseModel):
    status: str
    files_total: int
    files_indexed: int


class FolderListResponse(BaseModel):
    folders: list[FolderResponse]


class SyncResult(BaseModel):
    synced: bool
    added: int = 0
    modified: int = 0
    deleted: int = 0
    reason: str | None = None


@router.get("", response_model=FolderListResponse)
async def list_folders(
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """List all folders for the current user."""
    result = await db.execute(select(Folder).where(Folder.user_id == session.user_id))
    folders = result.scalars().all()

    return FolderListResponse(
        folders=[
            FolderResponse(
                id=str(f.id),
                google_folder_id=f.google_folder_id,
                folder_name=f.folder_name or "",
                index_status=f.index_status,
                files_total=f.files_total,
                files_indexed=f.files_indexed,
                last_synced_at=f.last_synced_at.isoformat() if f.last_synced_at else None,
            )
            for f in folders
        ]
    )


@router.post("", response_model=FolderResponse)
async def create_folder(
    folder: FolderCreate,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Create a new folder and start indexing."""
    # Create the folder record
    new_folder = Folder(
        user_id=session.user_id,
        google_folder_id=folder.google_folder_id,
        folder_name=folder.folder_name,
        index_status="indexing",
    )
    db.add(new_folder)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="This folder has already been added",
        ) from None

    # List files from Google Drive and create file records + indexing jobs
    drive = DriveService(session.access_token)
    files = []
    page_token = None

    while True:
        file_batch, page_token = await drive.list_files(folder.google_folder_id, page_token)
        files.extend(file_batch)
        if not page_token:
            break

    new_folder.files_total = len(files)

    # Create file records
    file_records = []
    for file_meta in files:
        file_record = File(
            folder_id=new_folder.id,
            google_file_id=file_meta.id,
            file_name=file_meta.name,
            mime_type=file_meta.mime_type,
            index_status="pending",
        )
        db.add(file_record)
        file_records.append(file_record)

    # Commit FIRST - file records guaranteed to exist
    await db.commit()

    # Dispatch Celery tasks AFTER commit succeeds
    dispatch_errors = []
    for file_record in file_records:
        try:
            process_indexing_job.delay(
                file_id=str(file_record.id),
                folder_id=str(new_folder.id),
                user_id=str(session.user_id),
            )
        except Exception as e:
            dispatch_errors.append((file_record.id, str(e)))

    if dispatch_errors:
        logger.error(f"Failed to dispatch {len(dispatch_errors)} tasks: {dispatch_errors}")

    return FolderResponse(
        id=str(new_folder.id),
        google_folder_id=new_folder.google_folder_id,
        folder_name=new_folder.folder_name or "",
        index_status=new_folder.index_status,
        files_total=new_folder.files_total,
        files_indexed=new_folder.files_indexed,
        last_synced_at=new_folder.last_synced_at.isoformat() if new_folder.last_synced_at else None,
    )


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Get folder details including file list."""
    try:
        folder_uuid = uuid.UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID") from None

    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_uuid,
            Folder.user_id == session.user_id,
        )
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    return FolderResponse(
        id=str(folder.id),
        google_folder_id=folder.google_folder_id,
        folder_name=folder.folder_name or "",
        index_status=folder.index_status,
        files_total=folder.files_total,
        files_indexed=folder.files_indexed,
        last_synced_at=folder.last_synced_at.isoformat() if folder.last_synced_at else None,
    )


@router.get("/{folder_id}/status", response_model=FolderStatus)
async def get_folder_status(
    folder_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Get folder indexing status (for polling)."""
    try:
        folder_uuid = uuid.UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID") from None

    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_uuid,
            Folder.user_id == session.user_id,
        )
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    return FolderStatus(
        status=folder.index_status,
        files_total=folder.files_total,
        files_indexed=folder.files_indexed,
    )


@router.post("/{folder_id}/sync", response_model=SyncResult)
async def sync_folder(
    folder_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Trigger background sync with Google Drive."""
    try:
        folder_uuid = uuid.UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID") from None

    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_uuid,
            Folder.user_id == session.user_id,
        )
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    sync_result = await sync_folder_if_needed(
        db=db,
        folder=folder,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
    )

    return SyncResult(
        synced=sync_result.get("synced", False),
        added=sync_result.get("added", 0),
        modified=sync_result.get("modified", 0),
        deleted=sync_result.get("deleted", 0),
        reason=sync_result.get("reason"),
    )
