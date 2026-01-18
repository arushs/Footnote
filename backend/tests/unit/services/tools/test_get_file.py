"""Tests for get_file tool definition."""

from app.services.tools import GET_FILE_TOOL


class TestGetFileTool:
    """Tests for the get_file tool definition."""

    def test_tool_has_required_fields(self):
        """Tool should have name, description, and input_schema."""
        assert "name" in GET_FILE_TOOL
        assert "description" in GET_FILE_TOOL
        assert "input_schema" in GET_FILE_TOOL

    def test_tool_name_is_get_file(self):
        """Tool name should be get_file."""
        assert GET_FILE_TOOL["name"] == "get_file"

    def test_tool_requires_file_id(self):
        """Tool should require file_id parameter."""
        schema = GET_FILE_TOOL["input_schema"]
        assert "file_id" in schema["properties"]
        assert "file_id" in schema["required"]

    def test_file_id_is_string(self):
        """File ID parameter should be a string."""
        schema = GET_FILE_TOOL["input_schema"]
        assert schema["properties"]["file_id"]["type"] == "string"

    def test_description_mentions_slower(self):
        """Description should mention this is slower."""
        desc = GET_FILE_TOOL["description"].lower()
        assert "slow" in desc

    def test_description_mentions_google_drive(self):
        """Description should mention Google Drive."""
        desc = GET_FILE_TOOL["description"].lower()
        assert "google" in desc or "drive" in desc
