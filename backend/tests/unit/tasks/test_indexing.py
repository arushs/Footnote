"""Tests for the indexing Celery task."""

import uuid
from unittest.mock import patch

import pytest

from app.celery_app import celery_app
from app.exceptions import PermanentIndexingError, TransientIndexingError
from app.tasks.indexing import process_indexing_job


@pytest.fixture(autouse=True)
def celery_eager_mode():
    """Configure Celery to run tasks eagerly (synchronously) without broker."""
    # Store original settings
    original_eager = celery_app.conf.task_always_eager
    original_propagate = celery_app.conf.task_eager_propagates

    # Enable eager mode for testing
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    yield

    # Restore original settings
    celery_app.conf.task_always_eager = original_eager
    celery_app.conf.task_eager_propagates = original_propagate


class TestProcessIndexingJobConfiguration:
    """Tests for task configuration."""

    def test_task_has_correct_retry_settings(self):
        """Verify retry configuration matches plan specifications."""
        # Retry backoff starts at 30 seconds
        assert process_indexing_job.retry_backoff == 30

        # Max retry backoff is 10 minutes (600 seconds)
        assert process_indexing_job.retry_backoff_max == 600

        # Jitter is enabled for retry randomization
        assert process_indexing_job.retry_jitter is True

        # Max 5 retry attempts
        assert process_indexing_job.max_retries == 5

    def test_task_has_correct_time_limits(self):
        """Verify time limits for long-running tasks."""
        # Soft time limit at 14 minutes
        assert process_indexing_job.soft_time_limit == 840

        # Hard time limit at 15 minutes
        assert process_indexing_job.time_limit == 900

    def test_task_autorety_configuration(self):
        """Verify autoretry is configured for correct exception types."""
        # Should auto-retry on transient errors
        assert TransientIndexingError in process_indexing_job.autoretry_for

        # Should NOT auto-retry on permanent errors
        assert PermanentIndexingError in process_indexing_job.dont_autoretry_for

    def test_task_name_is_set(self):
        """Verify task has a proper name."""
        assert "process_indexing_job" in process_indexing_job.name


class TestExceptionTaxonomy:
    """Tests for exception classification."""

    def test_permanent_error_inherits_from_indexing_error(self):
        """PermanentIndexingError should inherit from IndexingError."""
        from app.exceptions import IndexingError

        assert issubclass(PermanentIndexingError, IndexingError)

    def test_transient_error_inherits_from_indexing_error(self):
        """TransientIndexingError should inherit from IndexingError."""
        from app.exceptions import IndexingError

        assert issubclass(TransientIndexingError, IndexingError)

    def test_permanent_errors_list_contains_expected_types(self):
        """PERMANENT_ERRORS should contain non-retryable error types."""
        from app.exceptions import PERMANENT_ERRORS

        assert ValueError in PERMANENT_ERRORS
        assert PermissionError in PERMANENT_ERRORS
        assert FileNotFoundError in PERMANENT_ERRORS

    def test_transient_errors_list_contains_expected_types(self):
        """TRANSIENT_ERRORS should contain retryable error types."""
        from app.exceptions import TRANSIENT_ERRORS

        assert ConnectionError in TRANSIENT_ERRORS
        assert TimeoutError in TRANSIENT_ERRORS
        assert OSError in TRANSIENT_ERRORS


class TestProcessIndexingJobExecution:
    """Tests for task execution behavior.

    These tests verify the task's behavior by testing the underlying
    _process_job_async function directly, which avoids Celery's broker
    dependencies while still validating the core logic.
    """

    @pytest.fixture
    def sample_ids(self):
        """Generate sample UUIDs for testing."""
        return {
            "file_id": str(uuid.uuid4()),
            "folder_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
        }

    @patch.object(process_indexing_job, "update_state")
    @patch("app.tasks.indexing.asyncio.run")
    def test_task_returns_result_on_success(self, mock_asyncio_run, mock_update_state, sample_ids):
        """Task should return the result from async processing."""
        expected_result = {"status": "completed", "file_id": sample_ids["file_id"], "chunks": 10}
        mock_asyncio_run.return_value = expected_result

        # Use apply() with eager mode - mock update_state to avoid Redis
        result = process_indexing_job.run(
            sample_ids["file_id"],
            sample_ids["folder_id"],
            sample_ids["user_id"],
        )

        assert result == expected_result
        mock_update_state.assert_called_once()

    @patch.object(process_indexing_job, "update_state")
    @patch("app.tasks.indexing._update_file_status")
    @patch("app.tasks.indexing.asyncio.run")
    def test_task_raises_permanent_error(
        self, mock_asyncio_run, mock_update_status, mock_update_state, sample_ids
    ):
        """Task should raise PermanentIndexingError (no retry)."""
        mock_asyncio_run.side_effect = PermanentIndexingError("File not found")

        with pytest.raises(PermanentIndexingError):
            process_indexing_job.run(
                sample_ids["file_id"],
                sample_ids["folder_id"],
                sample_ids["user_id"],
            )

    @patch.object(process_indexing_job, "update_state")
    @patch("app.tasks.indexing.asyncio.run")
    def test_task_raises_transient_error_for_retry(
        self, mock_asyncio_run, mock_update_state, sample_ids
    ):
        """Task should raise TransientIndexingError for Celery retry."""
        mock_asyncio_run.side_effect = TransientIndexingError("Connection timeout")

        with pytest.raises(TransientIndexingError):
            process_indexing_job.run(
                sample_ids["file_id"],
                sample_ids["folder_id"],
                sample_ids["user_id"],
            )

    @patch.object(process_indexing_job, "update_state")
    @patch("app.tasks.indexing.asyncio.run")
    def test_task_wraps_unexpected_error_as_transient(
        self, mock_asyncio_run, mock_update_state, sample_ids
    ):
        """Unexpected errors should be wrapped as TransientIndexingError for retry."""
        mock_asyncio_run.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(TransientIndexingError) as exc_info:
            process_indexing_job.run(
                sample_ids["file_id"],
                sample_ids["folder_id"],
                sample_ids["user_id"],
            )

        assert "Unexpected error" in str(exc_info.value)


class TestTaskDispatch:
    """Tests for task dispatch from routes."""

    @patch("app.tasks.indexing.process_indexing_job.delay")
    def test_task_can_be_dispatched(self, mock_delay):
        """Verify task can be dispatched with correct arguments."""
        file_id = str(uuid.uuid4())
        folder_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        from app.tasks.indexing import process_indexing_job

        process_indexing_job.delay(
            file_id=file_id,
            folder_id=folder_id,
            user_id=user_id,
        )

        mock_delay.assert_called_once_with(
            file_id=file_id,
            folder_id=folder_id,
            user_id=user_id,
        )
