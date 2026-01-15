"""Integration tests for folder management routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.db_models import File, Folder, IndexingJob


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
        result = await db_session.execute(
            select(File).where(File.folder_id == folder_id)
        )
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
    async def test_get_folder_returns_details(
        self, auth_client: AsyncClient, test_folder: Folder
    ):
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
        from app.models.db_models import Session, User
        from datetime import datetime, timedelta, timezone

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
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(other_session)
        await db_session.flush()

        client.cookies.set("session_id", str(other_session.id))
        response = await client.get(f"/api/folders/{test_folder.id}")

        assert response.status_code == 404


class TestGetFolderStatus:
    """Tests for getting folder indexing status."""

    @pytest.mark.asyncio
    async def test_get_folder_status_ready(
        self, auth_client: AsyncClient, test_folder: Folder
    ):
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


class TestDeleteFolder:
    """Tests for deleting folders."""

    @pytest.mark.asyncio
    async def test_delete_folder_success(
        self, auth_client: AsyncClient, db_session, test_folder: Folder
    ):
        """Test that deleting a folder removes it from database."""
        response = await auth_client.delete(f"/api/folders/{test_folder.id}")

        assert response.status_code == 200
        assert response.json()["message"] == "Folder deleted successfully"

        # Verify folder is deleted
        result = await db_session.execute(
            select(Folder).where(Folder.id == test_folder.id)
        )
        folder = result.scalar_one_or_none()
        assert folder is None

    @pytest.mark.asyncio
    async def test_delete_folder_cascades_to_files(
        self, auth_client: AsyncClient, db_session, test_folder: Folder, test_file: File
    ):
        """Test that deleting a folder also deletes associated files."""
        response = await auth_client.delete(f"/api/folders/{test_folder.id}")

        assert response.status_code == 200

        # Verify files are deleted
        result = await db_session.execute(
            select(File).where(File.folder_id == test_folder.id)
        )
        files = result.scalars().all()
        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_delete_folder_not_found(self, auth_client: AsyncClient):
        """Test that deleting nonexistent folder returns 404."""
        response = await auth_client.delete(f"/api/folders/{uuid.uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_folder_other_user_not_allowed(
        self, client: AsyncClient, db_session, test_folder: Folder
    ):
        """Test that user cannot delete another user's folder."""
        from app.models.db_models import Session, User
        from datetime import datetime, timedelta, timezone

        other_user = User(
            id=uuid.uuid4(),
            google_id="delete-other-google-id",
            email="delete-other@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_session = Session(
            id=uuid.uuid4(),
            user_id=other_user.id,
            access_token="other-token",
            refresh_token="other-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(other_session)
        await db_session.flush()

        client.cookies.set("session_id", str(other_session.id))
        response = await client.delete(f"/api/folders/{test_folder.id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_folder_requires_authentication(
        self, client: AsyncClient, test_folder: Folder
    ):
        """Test that deleting a folder requires authentication."""
        response = await client.delete(f"/api/folders/{test_folder.id}")

        assert response.status_code == 401
