"""Integration tests for folder management routes."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File, Folder, IndexingJob


class TestListFolders:
    """Tests for listing folders."""

    @pytest.mark.asyncio
    async def test_list_folders_returns_user_folders(
        self, auth_client: AsyncClient, test_folder: Folder
    ):
        """Test that list folders returns the user's folders."""
        response = await auth_client.get("/api/folders")

        assert response.status_code == 200
        data = response.json()
        assert "folders" in data
        assert len(data["folders"]) == 1
        assert data["folders"][0]["id"] == str(test_folder.id)
        assert data["folders"][0]["folder_name"] == "Test Folder"
        assert data["folders"][0]["index_status"] == "ready"

    @pytest.mark.asyncio
    async def test_list_folders_empty_for_new_user(self, auth_client: AsyncClient):
        """Test that list folders returns empty for user with no folders."""
        response = await auth_client.get("/api/folders")

        assert response.status_code == 200
        data = response.json()
        assert data["folders"] == []

    @pytest.mark.asyncio
    async def test_list_folders_requires_authentication(self, client: AsyncClient):
        """Test that list folders requires authentication."""
        response = await client.get("/api/folders")

        assert response.status_code == 401


class TestCreateFolder:
    """Tests for creating folders."""

    @pytest.mark.asyncio
    async def test_create_folder_success(
        self, auth_client: AsyncClient, db_session, mock_drive_service
    ):
        """Test that creating a folder lists files and creates indexing jobs."""
        with patch("app.routes.folders.DriveService", return_value=mock_drive_service):
            response = await auth_client.post(
                "/api/folders",
                json={
                    "google_folder_id": "new-folder-id",
                    "folder_name": "My New Folder",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["folder_name"] == "My New Folder"
        assert data["google_folder_id"] == "new-folder-id"
        assert data["index_status"] == "indexing"
        assert data["files_total"] == 2  # Mock returns 2 files

        # Verify files and indexing jobs were created
        folder_id = uuid.UUID(data["id"])
        result = await db_session.execute(select(File).where(File.folder_id == folder_id))
        files = result.scalars().all()
        assert len(files) == 2

        result = await db_session.execute(
            select(IndexingJob).where(IndexingJob.folder_id == folder_id)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 2
        assert all(job.status == "pending" for job in jobs)

    @pytest.mark.asyncio
    async def test_create_folder_requires_authentication(self, client: AsyncClient):
        """Test that creating a folder requires authentication."""
        response = await client.post(
            "/api/folders",
            json={
                "google_folder_id": "folder-id",
                "folder_name": "Folder",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_folder_handles_empty_folder(
        self, auth_client: AsyncClient, mock_drive_service
    ):
        """Test that creating a folder works with empty Google Drive folder."""
        mock_drive_service.list_files = AsyncMock(return_value=([], None))

        with patch("app.routes.folders.DriveService", return_value=mock_drive_service):
            response = await auth_client.post(
                "/api/folders",
                json={
                    "google_folder_id": "empty-folder-id",
                    "folder_name": "Empty Folder",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["files_total"] == 0


class TestGetFolder:
    """Tests for getting folder details."""

    @pytest.mark.asyncio
    async def test_get_folder_returns_details(self, auth_client: AsyncClient, test_folder: Folder):
        """Test that get folder returns folder details."""
        response = await auth_client.get(f"/api/folders/{test_folder.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_folder.id)
        assert data["folder_name"] == "Test Folder"
        assert data["index_status"] == "ready"
        assert data["files_total"] == 2
        assert data["files_indexed"] == 2

    @pytest.mark.asyncio
    async def test_get_folder_not_found(self, auth_client: AsyncClient):
        """Test that get folder returns 404 for nonexistent folder."""
        response = await auth_client.get(f"/api/folders/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Folder not found"

    @pytest.mark.asyncio
    async def test_get_folder_invalid_uuid(self, auth_client: AsyncClient):
        """Test that get folder returns 400 for invalid UUID."""
        response = await auth_client.get("/api/folders/not-a-uuid")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid folder ID"

    @pytest.mark.asyncio
    async def test_get_folder_other_user_not_found(
        self, client: AsyncClient, db_session, test_folder: Folder
    ):
        """Test that user cannot access another user's folder."""
        # Create another user and session
        from datetime import datetime, timedelta

        from app.models import Session, User

        other_user = User(
            id=uuid.uuid4(),
            google_id="other-google-id",
            email="other@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_session = Session(
            id=uuid.uuid4(),
            user_id=other_user.id,
            access_token="other-token",
            refresh_token="other-refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db_session.add(other_session)
        await db_session.flush()

        client.cookies.set("session_id", str(other_session.id))
        response = await client.get(f"/api/folders/{test_folder.id}")

        assert response.status_code == 404


class TestGetFolderStatus:
    """Tests for getting folder indexing status."""

    @pytest.mark.asyncio
    async def test_get_folder_status_ready(self, auth_client: AsyncClient, test_folder: Folder):
        """Test that status returns ready for indexed folder."""
        response = await auth_client.get(f"/api/folders/{test_folder.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["files_total"] == 2
        assert data["files_indexed"] == 2

    @pytest.mark.asyncio
    async def test_get_folder_status_indexing(
        self, auth_client: AsyncClient, indexing_folder: Folder
    ):
        """Test that status returns indexing for folder in progress."""
        response = await auth_client.get(f"/api/folders/{indexing_folder.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexing"
        assert data["files_total"] == 5
        assert data["files_indexed"] == 2

    @pytest.mark.asyncio
    async def test_get_folder_status_not_found(self, auth_client: AsyncClient):
        """Test that status returns 404 for nonexistent folder."""
        response = await auth_client.get(f"/api/folders/{uuid.uuid4()}/status")

        assert response.status_code == 404


class TestFolderLastSyncedAt:
    """Tests for folder last_synced_at field."""

    @pytest.fixture
    async def synced_folder(self, db_session: AsyncSession, test_user) -> Folder:
        """Create a folder with last_synced_at set."""
        folder = Folder(
            id=uuid.uuid4(),
            user_id=test_user.id,
            google_folder_id="synced-folder-id",
            folder_name="Synced Folder",
            index_status="ready",
            files_total=3,
            files_indexed=3,
            last_synced_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(folder)
        await db_session.flush()
        return folder

    @pytest.mark.asyncio
    async def test_list_folders_includes_last_synced_at(
        self, auth_client: AsyncClient, synced_folder: Folder
    ):
        """Test that list folders returns last_synced_at field."""
        response = await auth_client.get("/api/folders")

        assert response.status_code == 200
        data = response.json()
        assert len(data["folders"]) == 1
        folder_data = data["folders"][0]
        assert "last_synced_at" in folder_data
        assert folder_data["last_synced_at"] is not None
        # Verify it's a valid ISO format datetime
        datetime.fromisoformat(folder_data["last_synced_at"].replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_get_folder_includes_last_synced_at(
        self, auth_client: AsyncClient, synced_folder: Folder
    ):
        """Test that get folder returns last_synced_at field."""
        response = await auth_client.get(f"/api/folders/{synced_folder.id}")

        assert response.status_code == 200
        data = response.json()
        assert "last_synced_at" in data
        assert data["last_synced_at"] is not None

    @pytest.mark.asyncio
    async def test_folder_without_sync_returns_null_last_synced_at(
        self, auth_client: AsyncClient, test_folder: Folder
    ):
        """Test that folder without sync has null last_synced_at."""
        response = await auth_client.get(f"/api/folders/{test_folder.id}")

        assert response.status_code == 200
        data = response.json()
        assert "last_synced_at" in data
        assert data["last_synced_at"] is None

    @pytest.mark.asyncio
    async def test_create_folder_returns_null_last_synced_at(
        self, auth_client: AsyncClient, mock_drive_service
    ):
        """Test that newly created folder has null last_synced_at."""
        with patch("app.routes.folders.DriveService", return_value=mock_drive_service):
            response = await auth_client.post(
                "/api/folders",
                json={
                    "google_folder_id": "new-folder-id",
                    "folder_name": "New Folder",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "last_synced_at" in data
        assert data["last_synced_at"] is None


class TestSyncFolder:
    """Tests for syncing folders with Google Drive."""

    @pytest.mark.asyncio
    async def test_sync_folder_skips_recent_sync(
        self, auth_client: AsyncClient, db_session: AsyncSession, test_user
    ):
        """Test that sync is skipped if folder was synced recently."""
        # Create a folder with recent last_synced_at
        folder = Folder(
            id=uuid.uuid4(),
            user_id=test_user.id,
            google_folder_id="recently-synced-folder",
            folder_name="Recently Synced",
            index_status="ready",
            files_total=2,
            files_indexed=2,
            last_synced_at=datetime.now(UTC) - timedelta(minutes=30),  # 30 min ago
        )
        db_session.add(folder)
        await db_session.flush()

        response = await auth_client.post(f"/api/folders/{folder.id}/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["synced"] is False
        assert data["reason"] == "recent_sync"

    @pytest.mark.asyncio
    async def test_sync_folder_not_found(self, auth_client: AsyncClient):
        """Test that sync returns 404 for nonexistent folder."""
        response = await auth_client.post(f"/api/folders/{uuid.uuid4()}/sync")

        assert response.status_code == 404
        assert response.json()["detail"] == "Folder not found"

    @pytest.mark.asyncio
    async def test_sync_folder_invalid_uuid(self, auth_client: AsyncClient):
        """Test that sync returns 400 for invalid UUID."""
        response = await auth_client.post("/api/folders/not-a-uuid/sync")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid folder ID"

    @pytest.mark.asyncio
    async def test_sync_folder_requires_authentication(
        self, client: AsyncClient, test_folder: Folder
    ):
        """Test that sync requires authentication."""
        response = await client.post(f"/api/folders/{test_folder.id}/sync")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_sync_folder_triggers_sync_when_stale(
        self, auth_client: AsyncClient, db_session: AsyncSession, test_user, mock_drive_service
    ):
        """Test that sync triggers when folder hasn't been synced recently."""
        # Create a folder with old last_synced_at
        folder = Folder(
            id=uuid.uuid4(),
            user_id=test_user.id,
            google_folder_id="stale-folder",
            folder_name="Stale Folder",
            index_status="ready",
            files_total=2,
            files_indexed=2,
            last_synced_at=datetime.now(UTC) - timedelta(hours=2),  # 2 hours ago
        )
        db_session.add(folder)
        await db_session.flush()

        # Mock the sync service to return no changes
        with patch("app.routes.folders.sync_folder_if_needed", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {
                "synced": True,
                "added": 0,
                "modified": 0,
                "deleted": 0,
            }
            response = await auth_client.post(f"/api/folders/{folder.id}/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["synced"] is True
        assert data["added"] == 0
        assert data["modified"] == 0
        assert data["deleted"] == 0
        mock_sync.assert_called_once()
