"""Tests for Dead Letter Queue (DLQ) task base class."""

from unittest.mock import MagicMock, patch

import pytest

from app.tasks.base import DLQTask


class TestDLQTaskConfiguration:
    """Tests for DLQTask configuration."""

    def test_dlq_task_inherits_from_celery_task(self):
        """DLQTask should inherit from Celery Task."""
        from celery import Task

        assert issubclass(DLQTask, Task)

    def test_dlq_task_has_on_failure_method(self):
        """DLQTask should have on_failure method."""
        assert hasattr(DLQTask, "on_failure")
        assert callable(DLQTask.on_failure)


class TestDLQTaskOnFailure:
    """Tests for DLQTask.on_failure behavior."""

    @pytest.fixture
    def sample_exception(self):
        """Create a sample exception."""
        try:
            raise ValueError("Test error message")
        except ValueError as e:
            return e

    @pytest.fixture
    def sample_einfo(self):
        """Create a mock exception info object."""
        einfo = MagicMock()
        einfo.traceback = "Traceback (most recent call last):\n  File ...\nValueError: Test error"
        return einfo

    @patch("app.tasks.base.celery_session_scope")
    def test_on_failure_creates_failed_task_record(
        self, mock_session_scope, sample_exception, sample_einfo
    ):
        """on_failure should create a FailedTask record in the database."""
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Create task and mock request property
        task = DLQTask()
        task.name = "test_task"
        mock_request = MagicMock()
        mock_request.retries = 3
        with patch.object(
            DLQTask, "request", new_callable=lambda: property(lambda self: mock_request)
        ):
            task.on_failure(
                exc=sample_exception,
                task_id="test-task-id-123",
                args=["arg1", "arg2"],
                kwargs={"key": "value"},
                einfo=sample_einfo,
            )

        # Verify session.add was called
        mock_session.add.assert_called_once()

        # Verify the FailedTask object has correct attributes
        failed_task = mock_session.add.call_args[0][0]
        assert failed_task.task_id == "test-task-id-123"
        assert failed_task.task_name == "test_task"
        assert failed_task.args == ["arg1", "arg2"]
        assert failed_task.kwargs == {"key": "value"}
        assert failed_task.exception_type == "ValueError"
        assert failed_task.exception_message == "Test error message"

    @patch("app.tasks.base.celery_session_scope")
    def test_on_failure_updates_existing_record(
        self, mock_session_scope, sample_exception, sample_einfo
    ):
        """on_failure should update existing record if task_id already exists."""
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_scope.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate existing record
        existing_record = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = existing_record

        task = DLQTask()
        task.name = "test_task"
        mock_request = MagicMock()
        mock_request.retries = 3
        with patch.object(
            DLQTask, "request", new_callable=lambda: property(lambda self: mock_request)
        ):
            task.on_failure(
                exc=sample_exception,
                task_id="existing-task-id",
                args=[],
                kwargs={},
                einfo=sample_einfo,
            )

        # Should update existing record, not add new one
        mock_session.add.assert_not_called()
        assert existing_record.exception_type == "ValueError"
        assert existing_record.exception_message == "Test error message"

    @patch("app.tasks.base.celery_session_scope")
    def test_on_failure_handles_none_args_kwargs(
        self, mock_session_scope, sample_exception, sample_einfo
    ):
        """on_failure should handle None args and kwargs."""
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        task = DLQTask()
        task.name = "test_task"
        mock_request = MagicMock()
        mock_request.retries = 0
        with patch.object(
            DLQTask, "request", new_callable=lambda: property(lambda self: mock_request)
        ):
            task.on_failure(
                exc=sample_exception,
                task_id="test-task-id",
                args=None,
                kwargs=None,
                einfo=sample_einfo,
            )

        failed_task = mock_session.add.call_args[0][0]
        assert failed_task.args is None
        assert failed_task.kwargs is None

    @patch("app.tasks.base.celery_session_scope")
    def test_on_failure_handles_none_einfo(self, mock_session_scope, sample_exception):
        """on_failure should handle None einfo (no traceback)."""
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        task = DLQTask()
        task.name = "test_task"
        mock_request = MagicMock()
        mock_request.retries = 0
        with patch.object(
            DLQTask, "request", new_callable=lambda: property(lambda self: mock_request)
        ):
            task.on_failure(
                exc=sample_exception,
                task_id="test-task-id",
                args=[],
                kwargs={},
                einfo=None,
            )

        failed_task = mock_session.add.call_args[0][0]
        assert failed_task.traceback is None

    @patch("app.tasks.base.celery_session_scope")
    @patch("app.tasks.base.logger")
    def test_on_failure_logs_error(
        self, mock_logger, mock_session_scope, sample_exception, sample_einfo
    ):
        """on_failure should log the failure."""
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        task = DLQTask()
        task.name = "test_task"
        mock_request = MagicMock()
        mock_request.retries = 0
        with patch.object(
            DLQTask, "request", new_callable=lambda: property(lambda self: mock_request)
        ):
            task.on_failure(
                exc=sample_exception,
                task_id="test-task-id",
                args=[],
                kwargs={},
                einfo=sample_einfo,
            )

        mock_logger.error.assert_called()

    @patch("app.tasks.base.celery_session_scope")
    @patch("app.tasks.base.logger")
    def test_on_failure_handles_db_error_gracefully(
        self, mock_logger, mock_session_scope, sample_exception, sample_einfo
    ):
        """on_failure should not crash if database save fails."""
        mock_session_scope.side_effect = Exception("Database connection failed")

        task = DLQTask()
        task.name = "test_task"
        mock_request = MagicMock()
        mock_request.retries = 0
        with patch.object(
            DLQTask, "request", new_callable=lambda: property(lambda self: mock_request)
        ):
            # Should not raise, just log the error
            task.on_failure(
                exc=sample_exception,
                task_id="test-task-id",
                args=[],
                kwargs={},
                einfo=sample_einfo,
            )

        # Should log the DLQ save failure
        assert any("Failed to save" in str(call) for call in mock_logger.error.call_args_list)


class TestIndexingTaskUsesDLQ:
    """Tests to verify indexing task uses DLQ base class."""

    def test_indexing_task_has_on_failure_method(self):
        """process_indexing_job should have on_failure method from DLQTask."""
        from app.tasks.indexing import process_indexing_job

        # The task should have on_failure from DLQTask
        assert hasattr(process_indexing_job, "on_failure")
        assert callable(process_indexing_job.on_failure)
