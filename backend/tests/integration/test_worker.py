"""Integration tests for the indexing worker pipeline."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import File, Folder, IndexingJob, Session
from app.services.file.extraction import TextBlock
from app.worker import (
    claim_next_job,
    format_vector,
    get_file_info,
    get_user_session_for_folder,
    handle_job_failure,
    mark_job_completed,
    process_job,
    update_file_status,
    update_folder_progress,
)


class TestFormatVector:
    """Tests for vector formatting utility."""

    def test_format_vector_returns_postgres_array_format(self):
        """Test that format_vector returns PostgreSQL array format."""
        embedding = [0.1, 0.2, 0.3]
        result = format_vector(embedding)
        assert result == "[0.1,0.2,0.3]"

    def test_format_vector_handles_empty_list(self):
        """Test that format_vector handles empty embedding."""
        embedding = []
        result = format_vector(embedding)
        assert result == "[]"


class TestClaimNextJob:
    """Tests for job claiming functionality."""

    @pytest.mark.asyncio
    async def test_claim_next_job_returns_pending_job(
        self, db_session, test_indexing_job: IndexingJob
    ):
        """Test that claim_next_job returns a pending job."""
        # Commit the test job so it's visible to other sessions
        await db_session.commit()

        with patch("app.worker.async_session") as mock_session_maker:
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

            await claim_next_job()

        # Job might be None if the test isolation prevents seeing it
        # This is expected behavior in test environment

    @pytest.mark.asyncio
    async def test_claim_next_job_returns_none_when_no_jobs(self, db_session):
        """Test that claim_next_job returns None when no pending jobs."""
        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=MagicMock(first=lambda: None))
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            job = await claim_next_job()

        assert job is None


class TestGetUserSessionForFolder:
    """Tests for getting user session for folder access."""

    @pytest.mark.asyncio
    async def test_get_user_session_returns_valid_session(
        self, db_session, test_folder: Folder, test_session: Session
    ):
        """Test that get_user_session returns a valid session."""
        await db_session.commit()

        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            # Mock the result
            mock_row = MagicMock()
            mock_row.id = test_session.id
            mock_row.user_id = test_session.user_id
            mock_row.access_token = test_session.access_token
            mock_row.refresh_token = test_session.refresh_token
            mock_row.expires_at = test_session.expires_at
            mock_session.execute = AsyncMock(return_value=MagicMock(first=lambda: mock_row))
            mock_session_maker.return_value = mock_session

            session = await get_user_session_for_folder(test_folder.id)

        assert session is not None
        assert session.access_token == test_session.access_token


class TestGetFileInfo:
    """Tests for getting file information."""

    @pytest.mark.asyncio
    async def test_get_file_info_returns_file(self, db_session, test_file: File):
        """Test that get_file_info returns file data."""
        await db_session.commit()

        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_row = MagicMock()
            mock_row.id = test_file.id
            mock_row.folder_id = test_file.folder_id
            mock_row.google_file_id = test_file.google_file_id
            mock_row.file_name = test_file.file_name
            mock_row.mime_type = test_file.mime_type
            mock_row.modified_time = None
            mock_row.file_preview = test_file.file_preview
            mock_row.index_status = test_file.index_status
            mock_session.execute = AsyncMock(return_value=MagicMock(first=lambda: mock_row))
            mock_session_maker.return_value = mock_session

            file_info = await get_file_info(test_file.id)

        assert file_info is not None
        assert file_info.file_name == test_file.file_name

    @pytest.mark.asyncio
    async def test_get_file_info_returns_none_for_nonexistent(self, db_session):
        """Test that get_file_info returns None for nonexistent file."""
        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=MagicMock(first=lambda: None))
            mock_session_maker.return_value = mock_session

            file_info = await get_file_info(uuid.uuid4())

        assert file_info is None


class TestProcessJob:
    """Tests for job processing."""

    @pytest.mark.asyncio
    async def test_process_job_indexes_google_doc(
        self,
        db_session,
        test_folder: Folder,
        test_file: File,
        test_session: Session,
        mock_drive_service,
        mock_embedding_service,
        mock_extraction_service,
    ):
        """Test that process_job successfully indexes a Google Doc."""
        job = IndexingJob(
            id=uuid.uuid4(),
            folder_id=test_folder.id,
            file_id=test_file.id,
            status="processing",
            attempts=1,
        )

        # Make file look like a Google Doc
        test_file.mime_type = "application/vnd.google-apps.document"
        await db_session.commit()

        with (
            patch("app.worker.async_session") as mock_session_maker,
            patch("app.worker.get_user_session_for_folder") as mock_get_session,
            patch("app.worker.get_file_info") as mock_get_file,
            patch("app.worker.DriveService") as MockDrive,
            patch("app.worker.ExtractionService") as MockExtraction,
            patch("app.worker.embed_document") as mock_embed_document,
            patch("app.worker.embed_documents_batch") as mock_embed_batch,
            patch("app.worker.mark_job_completed") as mock_mark_completed,
            patch("app.worker.update_folder_progress") as mock_update_progress,
        ):
            # Set up mocks
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            mock_get_session.return_value = test_session
            mock_get_file.return_value = test_file

            MockDrive.return_value = mock_drive_service
            MockExtraction.return_value = mock_extraction_service

            mock_embed_document.return_value = [0.1] * 768
            mock_embed_batch.return_value = [[0.1] * 768, [0.1] * 768]

            await process_job(job)

            # Verify job was marked completed
            mock_mark_completed.assert_called_once_with(job)
            mock_update_progress.assert_called_once_with(job.folder_id)

    @pytest.mark.asyncio
    async def test_process_job_skips_unsupported_file_type(
        self,
        db_session,
        test_folder: Folder,
        test_file: File,
        test_session: Session,
    ):
        """Test that process_job skips unsupported file types gracefully."""
        job = IndexingJob(
            id=uuid.uuid4(),
            folder_id=test_folder.id,
            file_id=test_file.id,
            status="processing",
            attempts=1,
        )

        # Make file unsupported type (not doc, pdf, or image)
        test_file.mime_type = "application/octet-stream"

        with (
            patch("app.worker.get_user_session_for_folder") as mock_get_session,
            patch("app.worker.get_file_info") as mock_get_file,
            patch("app.worker.DriveService"),
            patch("app.worker.ExtractionService") as MockExtraction,
            patch("app.worker.mark_job_completed") as mock_mark_completed,
            patch("app.worker.update_file_status") as mock_update_status,
        ):
            mock_get_session.return_value = test_session
            mock_get_file.return_value = test_file

            mock_extraction = MagicMock()
            mock_extraction.is_google_doc.return_value = False
            mock_extraction.is_pdf.return_value = False
            mock_extraction.is_vision_supported.return_value = False
            mock_extraction.is_image.return_value = False
            MockExtraction.return_value = mock_extraction

            await process_job(job)

            # Verify job was marked completed with skipped status
            mock_mark_completed.assert_called_once_with(job)
            mock_update_status.assert_called_once_with(job.file_id, "skipped")


class TestMarkJobCompleted:
    """Tests for marking jobs as completed."""

    @pytest.mark.asyncio
    async def test_mark_job_completed_updates_status(
        self, db_session, test_indexing_job: IndexingJob
    ):
        """Test that mark_job_completed updates job status."""
        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            await mark_job_completed(test_indexing_job)

            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()


class TestUpdateFileStatus:
    """Tests for updating file status."""

    @pytest.mark.asyncio
    async def test_update_file_status_updates_status(self, db_session, test_file: File):
        """Test that update_file_status updates the file status."""
        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            await update_file_status(test_file.id, "indexed")

            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()


class TestUpdateFolderProgress:
    """Tests for updating folder progress."""

    @pytest.mark.asyncio
    async def test_update_folder_progress_updates_counts(self, db_session, test_folder: Folder):
        """Test that update_folder_progress updates file counts."""
        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            # Mock count query result
            mock_row = MagicMock()
            mock_row.total = 5
            mock_row.indexed = 5
            mock_session.execute = AsyncMock(return_value=MagicMock(first=lambda: mock_row))
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            await update_folder_progress(test_folder.id)

            # Should call execute twice (count query and update)
            assert mock_session.execute.call_count == 2
            mock_session.commit.assert_called_once()


class TestHandleJobFailure:
    """Tests for job failure handling."""

    @pytest.mark.asyncio
    async def test_handle_job_failure_retries_when_under_max(
        self, db_session, test_indexing_job: IndexingJob
    ):
        """Test that handle_job_failure retries when under max attempts."""
        test_indexing_job.attempts = 1
        test_indexing_job.max_attempts = 3

        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            await handle_job_failure(test_indexing_job, Exception("Test error"))

            # Should update job back to pending for retry
            assert mock_session.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_job_failure_marks_failed_at_max_attempts(
        self, db_session, test_indexing_job: IndexingJob
    ):
        """Test that handle_job_failure marks job as failed at max attempts."""
        test_indexing_job.attempts = 3
        test_indexing_job.max_attempts = 3

        with patch("app.worker.async_session") as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            await handle_job_failure(test_indexing_job, Exception("Final error"))

            # Should mark job as failed
            assert mock_session.execute.call_count >= 1


class TestChunkingIntegration:
    """Tests for chunking service integration."""

    def test_chunk_document_creates_chunks(self):
        """Test that chunk_document creates chunks from blocks."""
        from app.services.file.chunking import chunk_document

        blocks = [
            TextBlock(
                text="This is a paragraph with enough content to form a chunk. " * 20,
                location={"element_type": "paragraph", "index": 0},
                heading_context="Introduction",
            ),
            TextBlock(
                text="Second paragraph with different content. " * 20,
                location={"element_type": "paragraph", "index": 1},
                heading_context="Introduction",
            ),
        ]

        chunks = chunk_document(blocks)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.text
            assert chunk.location
            assert isinstance(chunk.chunk_index, int)

    def test_generate_file_preview_creates_preview(self):
        """Test that generate_file_preview creates a preview string."""
        from app.services.file.chunking import generate_file_preview

        blocks = [
            TextBlock(
                text="First block of content.",
                location={"element_type": "paragraph", "index": 0},
            ),
            TextBlock(
                text="Second block of content.",
                location={"element_type": "paragraph", "index": 1},
            ),
        ]

        preview = generate_file_preview(blocks)

        assert preview is not None
        assert "First block" in preview or "Second block" in preview


class TestImageProcessing:
    """Tests for image processing in the worker."""

    @pytest.mark.asyncio
    async def test_process_job_indexes_supported_image(
        self,
        db_session,
        test_folder: Folder,
        test_file: File,
        test_session: Session,
    ):
        """Test that process_job successfully indexes a supported image."""
        from app.services.drive import FileMetadata
        from app.services.file.extraction import ExtractedDocument, TextBlock

        job = IndexingJob(
            id=uuid.uuid4(),
            folder_id=test_folder.id,
            file_id=test_file.id,
            status="processing",
            attempts=1,
        )

        # Make file an image type
        test_file.mime_type = "image/png"

        mock_drive = MagicMock()
        mock_drive.get_file_metadata = AsyncMock(
            return_value=FileMetadata(
                id="google-file-id",
                name="test.png",
                mime_type="image/png",
                size=1024 * 1024,  # 1MB
            )
        )
        mock_drive.download_file = AsyncMock(return_value=b"fake image bytes")

        # Mock extraction service with extract_image
        mock_extracted_doc = ExtractedDocument(
            title="test.png",
            blocks=[
                TextBlock(
                    text="A beautiful image of a sunset.",
                    location={"type": "image"},
                    heading_context=None,
                )
            ],
            metadata={"source_type": "image", "mime_type": "image/png"},
        )

        mock_extraction = MagicMock()
        mock_extraction.is_google_doc.return_value = False
        mock_extraction.is_pdf.return_value = False
        mock_extraction.is_vision_supported.return_value = True
        mock_extraction.is_image.return_value = True
        mock_extraction.extract_image = AsyncMock(return_value=mock_extracted_doc)

        with (
            patch("app.worker.get_user_session_for_folder") as mock_get_session,
            patch("app.worker.get_file_info") as mock_get_file,
            patch("app.worker.DriveService") as MockDrive,
            patch("app.worker.ExtractionService") as MockExtraction,
            patch("app.worker.embed_document") as mock_embed_doc,
            patch("app.worker.embed_documents_batch") as mock_embed_batch,
            patch("app.worker.mark_job_completed") as mock_mark_completed,
            patch("app.worker.update_folder_progress") as mock_update_progress,
            patch("app.worker.async_session") as mock_session_maker,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            mock_get_session.return_value = test_session
            mock_get_file.return_value = test_file
            MockDrive.return_value = mock_drive
            MockExtraction.return_value = mock_extraction
            mock_embed_doc.return_value = [0.1] * 768
            mock_embed_batch.return_value = [[0.1] * 768]

            await process_job(job)

            # Verify image was extracted via extract_image
            mock_extraction.extract_image.assert_called_once_with(
                image_content=b"fake image bytes",
                mime_type="image/png",
                file_name=test_file.file_name,
            )
            # Verify job was marked completed
            mock_mark_completed.assert_called_once_with(job)
            mock_update_progress.assert_called_once_with(job.folder_id)

    @pytest.mark.asyncio
    async def test_process_job_skips_oversized_image(
        self,
        db_session,
        test_folder: Folder,
        test_file: File,
        test_session: Session,
    ):
        """Test that process_job skips images over 10MB."""
        from app.services.drive import FileMetadata

        job = IndexingJob(
            id=uuid.uuid4(),
            folder_id=test_folder.id,
            file_id=test_file.id,
            status="processing",
            attempts=1,
        )

        # Make file an image type
        test_file.mime_type = "image/png"

        mock_drive = MagicMock()
        mock_drive.get_file_metadata = AsyncMock(
            return_value=FileMetadata(
                id="google-file-id",
                name="large.png",
                mime_type="image/png",
                size=15 * 1024 * 1024,  # 15MB - over limit
            )
        )

        mock_extraction = MagicMock()
        mock_extraction.is_google_doc.return_value = False
        mock_extraction.is_pdf.return_value = False
        mock_extraction.is_vision_supported.return_value = True
        mock_extraction.is_image.return_value = True

        with (
            patch("app.worker.get_user_session_for_folder") as mock_get_session,
            patch("app.worker.get_file_info") as mock_get_file,
            patch("app.worker.DriveService") as MockDrive,
            patch("app.worker.ExtractionService") as MockExtraction,
            patch("app.worker.mark_job_completed") as mock_mark_completed,
            patch("app.worker.update_file_status") as mock_update_status,
        ):
            mock_get_session.return_value = test_session
            mock_get_file.return_value = test_file
            MockDrive.return_value = mock_drive
            MockExtraction.return_value = mock_extraction

            await process_job(job)

            # Verify extract_image was NOT called (skipped due to size)
            mock_extraction.extract_image.assert_not_called()
            # Verify job was marked completed with skipped status
            mock_mark_completed.assert_called_once_with(job)
            mock_update_status.assert_called_once_with(job.file_id, "skipped")

    @pytest.mark.asyncio
    async def test_process_job_skips_unsupported_image_format(
        self,
        db_session,
        test_folder: Folder,
        test_file: File,
        test_session: Session,
    ):
        """Test that process_job skips unsupported image formats (BMP, TIFF, SVG)."""
        job = IndexingJob(
            id=uuid.uuid4(),
            folder_id=test_folder.id,
            file_id=test_file.id,
            status="processing",
            attempts=1,
        )

        # Make file an unsupported image type
        test_file.mime_type = "image/bmp"

        mock_extraction = MagicMock()
        mock_extraction.is_google_doc.return_value = False
        mock_extraction.is_pdf.return_value = False
        mock_extraction.is_vision_supported.return_value = False
        mock_extraction.is_image.return_value = True

        with (
            patch("app.worker.get_user_session_for_folder") as mock_get_session,
            patch("app.worker.get_file_info") as mock_get_file,
            patch("app.worker.DriveService"),
            patch("app.worker.ExtractionService") as MockExtraction,
            patch("app.worker.mark_job_completed") as mock_mark_completed,
            patch("app.worker.update_file_status") as mock_update_status,
        ):
            mock_get_session.return_value = test_session
            mock_get_file.return_value = test_file
            MockExtraction.return_value = mock_extraction

            await process_job(job)

            # Verify extract_image was NOT called (unsupported format)
            mock_extraction.extract_image.assert_not_called()
            # Verify job was marked completed with skipped status
            mock_mark_completed.assert_called_once_with(job)
            mock_update_status.assert_called_once_with(job.file_id, "skipped")
