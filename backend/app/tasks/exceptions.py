"""Exception taxonomy for indexing errors.

Distinguishes between permanent errors (don't retry) and transient errors (retry with backoff).
"""


class IndexingError(Exception):
    """Base class for indexing errors."""

    pass


class PermanentIndexingError(IndexingError):
    """Errors that should NOT be retried.

    Examples: invalid file format, permission denied, file not found.
    """

    pass


class TransientIndexingError(IndexingError):
    """Errors that SHOULD be retried with backoff.

    Examples: network timeout, rate limiting, temporary API errors.
    """

    pass


# Map external exceptions to our taxonomy
PERMANENT_ERRORS = (
    ValueError,  # Invalid input/format
    PermissionError,  # Access denied
    FileNotFoundError,  # File doesn't exist
)

TRANSIENT_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network-related OS errors
)
