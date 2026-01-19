"""Tests for the utils module."""

import uuid

import pytest
from fastapi import HTTPException

from app.utils import validate_uuid


class TestValidateUuid:
    """Tests for UUID validation utility."""

    def test_valid_uuid(self):
        """Should return UUID for valid input."""
        valid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_uuid(valid)
        assert isinstance(result, uuid.UUID)
        assert str(result) == valid

    def test_valid_uuid_uppercase(self):
        """Should accept uppercase UUID."""
        valid = "550E8400-E29B-41D4-A716-446655440000"
        result = validate_uuid(valid)
        assert isinstance(result, uuid.UUID)

    def test_valid_uuid_no_dashes(self):
        """Should accept UUID without dashes."""
        valid = "550e8400e29b41d4a716446655440000"
        result = validate_uuid(valid)
        assert isinstance(result, uuid.UUID)

    def test_invalid_uuid_raises_400(self):
        """Should raise HTTPException 400 for invalid UUID."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("not-a-uuid")
        assert exc_info.value.status_code == 400
        assert "Invalid ID" in exc_info.value.detail

    def test_invalid_uuid_custom_name(self):
        """Should use custom name in error message."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("invalid", "folder ID")
        assert exc_info.value.status_code == 400
        assert "Invalid folder ID" in exc_info.value.detail

    def test_empty_string_raises(self):
        """Should raise for empty string."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("")
        assert exc_info.value.status_code == 400

    def test_partial_uuid_raises(self):
        """Should raise for partial UUID."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("550e8400-e29b-41d4")
        assert exc_info.value.status_code == 400

    def test_uuid_with_extra_chars_raises(self):
        """Should raise for UUID with extra characters."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("550e8400-e29b-41d4-a716-446655440000-extra")
        assert exc_info.value.status_code == 400
