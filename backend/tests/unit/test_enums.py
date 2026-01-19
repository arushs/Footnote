"""Tests for the enums module."""

from app.enums import FileStatus, FolderStatus, JobStatus


class TestFolderStatus:
    """Tests for FolderStatus enum."""

    def test_values_are_strings(self):
        """Enum values should be strings for database compatibility."""
        assert FolderStatus.PENDING == "pending"
        assert FolderStatus.INDEXING == "indexing"
        assert FolderStatus.READY == "ready"
        assert FolderStatus.ERROR == "error"

    def test_all_statuses_defined(self):
        """Should have all expected statuses."""
        statuses = {s.value for s in FolderStatus}
        assert statuses == {"pending", "indexing", "ready", "error"}

    def test_comparison_with_string(self):
        """Should be comparable with raw strings."""
        assert FolderStatus.READY == "ready"
        assert "pending" == FolderStatus.PENDING


class TestFileStatus:
    """Tests for FileStatus enum."""

    def test_values_are_strings(self):
        """Enum values should be strings for database compatibility."""
        assert FileStatus.PENDING == "pending"
        assert FileStatus.INDEXED == "indexed"
        assert FileStatus.SKIPPED == "skipped"
        assert FileStatus.FAILED == "failed"

    def test_all_statuses_defined(self):
        """Should have all expected statuses."""
        statuses = {s.value for s in FileStatus}
        assert statuses == {"pending", "indexed", "skipped", "failed"}


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_values_are_strings(self):
        """Enum values should be strings for database compatibility."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"

    def test_all_statuses_defined(self):
        """Should have all expected statuses."""
        statuses = {s.value for s in JobStatus}
        assert statuses == {"pending", "processing", "completed", "failed"}
