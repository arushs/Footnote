"""Tests for FailedTask model."""

from datetime import datetime

from app.models.failed_task import FailedTask


class TestFailedTaskModel:
    """Tests for FailedTask model structure."""

    def test_model_has_required_fields(self):
        """FailedTask should have all required fields."""
        # Check that model has required columns
        assert hasattr(FailedTask, "id")
        assert hasattr(FailedTask, "task_id")
        assert hasattr(FailedTask, "task_name")
        assert hasattr(FailedTask, "args")
        assert hasattr(FailedTask, "kwargs")
        assert hasattr(FailedTask, "exception_type")
        assert hasattr(FailedTask, "exception_message")
        assert hasattr(FailedTask, "traceback")
        assert hasattr(FailedTask, "retries")
        assert hasattr(FailedTask, "failed_at")
        assert hasattr(FailedTask, "resolved_at")
        assert hasattr(FailedTask, "resolution_notes")
        assert hasattr(FailedTask, "created_at")

    def test_model_table_name(self):
        """FailedTask should use correct table name."""
        assert FailedTask.__tablename__ == "failed_tasks"


class TestFailedTaskCreation:
    """Tests for creating FailedTask instances."""

    def test_create_failed_task_with_all_fields(self):
        """Should be able to create FailedTask with all fields."""
        task = FailedTask(
            task_id="celery-task-id-123",
            task_name="app.tasks.indexing.process_indexing_job",
            args=["file-id", "folder-id", "user-id"],
            kwargs={"key": "value"},
            exception_type="ValueError",
            exception_message="Something went wrong",
            traceback="Traceback ...",
            retries=5,
        )

        assert task.task_id == "celery-task-id-123"
        assert task.task_name == "app.tasks.indexing.process_indexing_job"
        assert task.args == ["file-id", "folder-id", "user-id"]
        assert task.kwargs == {"key": "value"}
        assert task.exception_type == "ValueError"
        assert task.exception_message == "Something went wrong"
        assert task.traceback == "Traceback ..."
        assert task.retries == 5

    def test_create_failed_task_with_minimal_fields(self):
        """Should be able to create FailedTask with only required fields."""
        task = FailedTask(
            task_id="task-123",
            task_name="test_task",
        )

        assert task.task_id == "task-123"
        assert task.task_name == "test_task"
        assert task.args is None
        assert task.kwargs is None
        assert task.resolved_at is None

    def test_retries_is_settable(self):
        """retries should be settable."""
        task = FailedTask(task_id="task-123", task_name="test_task", retries=5)
        assert task.retries == 5


class TestFailedTaskProperties:
    """Tests for FailedTask properties."""

    def test_is_resolved_false_when_resolved_at_none(self):
        """is_resolved should be False when resolved_at is None."""
        task = FailedTask(
            task_id="task-123",
            task_name="test_task",
            resolved_at=None,
        )

        assert task.is_resolved is False

    def test_is_resolved_true_when_resolved_at_set(self):
        """is_resolved should be True when resolved_at is set."""
        task = FailedTask(
            task_id="task-123",
            task_name="test_task",
            resolved_at=datetime.utcnow(),
        )

        assert task.is_resolved is True


class TestFailedTaskRepr:
    """Tests for FailedTask string representation."""

    def test_repr_includes_task_name_and_id(self):
        """__repr__ should include task name and task_id."""
        task = FailedTask(
            task_id="abc-123",
            task_name="my_task",
        )

        repr_str = repr(task)

        assert "my_task" in repr_str
        assert "abc-123" in repr_str
        assert "FailedTask" in repr_str


class TestFailedTaskExportedFromModels:
    """Tests to verify FailedTask is properly exported."""

    def test_failed_task_in_models_all(self):
        """FailedTask should be in models.__all__."""
        from app import models

        assert "FailedTask" in models.__all__

    def test_failed_task_importable_from_models(self):
        """FailedTask should be importable from app.models."""
        from app.models import FailedTask as ImportedFailedTask

        assert ImportedFailedTask is FailedTask
