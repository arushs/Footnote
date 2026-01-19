"""Enums for status values used throughout the application."""

from enum import StrEnum


class FolderStatus(StrEnum):
    """Status of a folder's indexing process."""

    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class FileStatus(StrEnum):
    """Status of an individual file's indexing process."""

    PENDING = "pending"
    INDEXED = "indexed"
    SKIPPED = "skipped"
    FAILED = "failed"


class JobStatus(StrEnum):
    """Status of an indexing job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
