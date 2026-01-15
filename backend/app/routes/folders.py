import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import Folder, File, IndexingJob, Session as DbSession, User
from app.routes.auth import get_current_session
from app.services.drive import DriveService

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


class FolderStatus(BaseModel):
    status: str
    files_total: int
    files_indexed: int


class FolderListResponse(BaseModel):
    folders: list[FolderResponse]


@router.get("", response_model=FolderListResponse)
async def list_folders(
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """List all folders for the current user."""
    result = await db.execute(
        select(Folder).where(Folder.user_id == session.user_id)
    )
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
    await db.flush()

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

    # Create file records and indexing jobs
    for file_meta in files:
        file_record = File(
            folder_id=new_folder.id,
            google_file_id=file_meta.id,
            file_name=file_meta.name,
            mime_type=file_meta.mime_type,
            index_status="pending",
        )
        db.add(file_record)
        await db.flush()

        # Create indexing job for this file
        job = IndexingJob(
            folder_id=new_folder.id,
            file_id=file_record.id,
            status="pending",
        )
        db.add(job)

    return FolderResponse(
        id=str(new_folder.id),
        google_folder_id=new_folder.google_folder_id,
        folder_name=new_folder.folder_name or "",
        index_status=new_folder.index_status,
        files_total=new_folder.files_total,
        files_indexed=new_folder.files_indexed,
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
        raise HTTPException(status_code=400, detail="Invalid folder ID")

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
        raise HTTPException(status_code=400, detail="Invalid folder ID")

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


