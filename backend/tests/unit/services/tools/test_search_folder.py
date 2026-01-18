"""Tests for search_folder tool definition."""

from app.services.tools import SEARCH_FOLDER_TOOL


class TestSearchFolderTool:
    """Tests for the search_folder tool definition."""

    def test_tool_has_required_fields(self):
        """Tool should have name, description, and input_schema."""
        assert "name" in SEARCH_FOLDER_TOOL
        assert "description" in SEARCH_FOLDER_TOOL
        assert "input_schema" in SEARCH_FOLDER_TOOL

    def test_tool_name_is_search_folder(self):
        """Tool name should be search_folder."""
        assert SEARCH_FOLDER_TOOL["name"] == "search_folder"

    def test_tool_description_mentions_hybrid_search(self):
        """Description should mention hybrid search."""
        desc = SEARCH_FOLDER_TOOL["description"].lower()
        assert "hybrid" in desc or "search" in desc

    def test_tool_requires_query_parameter(self):
        """Tool should require query parameter."""
        schema = SEARCH_FOLDER_TOOL["input_schema"]
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "required" in schema
        assert "query" in schema["required"]

    def test_query_parameter_is_string(self):
        """Query parameter should be a string."""
        schema = SEARCH_FOLDER_TOOL["input_schema"]
        assert schema["properties"]["query"]["type"] == "string"

    def test_description_includes_query_refinement_guidance(self):
        """Description should guide agent on query refinement."""
        desc = SEARCH_FOLDER_TOOL["description"].lower()
        # Should mention trying different terms when results are poor
        assert "different" in desc or "synonym" in desc or "alternative" in desc
