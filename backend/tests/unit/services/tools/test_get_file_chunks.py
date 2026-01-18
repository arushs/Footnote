"""Tests for get_file_chunks tool definition."""

from app.services.tools import GET_FILE_CHUNKS_TOOL


class TestGetFileChunksTool:
    """Tests for the get_file_chunks tool definition."""

    def test_tool_has_required_fields(self):
        """Tool should have name, description, and input_schema."""
        assert "name" in GET_FILE_CHUNKS_TOOL
        assert "description" in GET_FILE_CHUNKS_TOOL
        assert "input_schema" in GET_FILE_CHUNKS_TOOL

    def test_tool_name_is_get_file_chunks(self):
        """Tool name should be get_file_chunks."""
        assert GET_FILE_CHUNKS_TOOL["name"] == "get_file_chunks"

    def test_tool_requires_file_id(self):
        """Tool should require file_id parameter."""
        schema = GET_FILE_CHUNKS_TOOL["input_schema"]
        assert "file_id" in schema["properties"]
        assert "file_id" in schema["required"]

    def test_file_id_is_string(self):
        """File ID parameter should be a string."""
        schema = GET_FILE_CHUNKS_TOOL["input_schema"]
        assert schema["properties"]["file_id"]["type"] == "string"

    def test_description_mentions_fast_access(self):
        """Description should mention this is the fast option."""
        desc = GET_FILE_CHUNKS_TOOL["description"].lower()
        assert "fast" in desc

    def test_description_mentions_indexed_content(self):
        """Description should mention indexed/chunked content."""
        desc = GET_FILE_CHUNKS_TOOL["description"].lower()
        assert "indexed" in desc or "chunk" in desc
