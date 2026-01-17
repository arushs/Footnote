"""Tests for agent tool definitions."""

from app.services.tools import (
    ALL_TOOLS,
    GET_FILE_CHUNKS_TOOL,
    GET_FILE_TOOL,
    SEARCH_FOLDER_TOOL,
)


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


class TestAllTools:
    """Tests for the ALL_TOOLS list."""

    def test_all_tools_contains_three_tools(self):
        """ALL_TOOLS should contain exactly 3 tools."""
        assert len(ALL_TOOLS) == 3

    def test_all_tools_contains_search_folder(self):
        """ALL_TOOLS should include search_folder."""
        tool_names = [t["name"] for t in ALL_TOOLS]
        assert "search_folder" in tool_names

    def test_all_tools_contains_get_file_chunks(self):
        """ALL_TOOLS should include get_file_chunks."""
        tool_names = [t["name"] for t in ALL_TOOLS]
        assert "get_file_chunks" in tool_names

    def test_all_tools_contains_get_file(self):
        """ALL_TOOLS should include get_file."""
        tool_names = [t["name"] for t in ALL_TOOLS]
        assert "get_file" in tool_names

    def test_all_tools_does_not_contain_rewrite_query(self):
        """ALL_TOOLS should NOT include removed rewrite_query tool."""
        tool_names = [t["name"] for t in ALL_TOOLS]
        assert "rewrite_query" not in tool_names

    def test_all_tools_valid_json_schema(self):
        """All tools should have valid JSON schema format."""
        for tool in ALL_TOOLS:
            schema = tool["input_schema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema


class TestToolSchemaValidity:
    """Tests for overall tool schema validity."""

    def test_all_tools_have_descriptions(self):
        """All tools should have non-empty descriptions."""
        for tool in ALL_TOOLS:
            assert len(tool["description"]) > 50  # Meaningful description

    def test_all_required_params_exist_in_properties(self):
        """All required parameters should exist in properties."""
        for tool in ALL_TOOLS:
            schema = tool["input_schema"]
            for required_param in schema["required"]:
                assert required_param in schema["properties"]

    def test_all_params_have_descriptions(self):
        """All parameters should have descriptions."""
        for tool in ALL_TOOLS:
            for _param, spec in tool["input_schema"]["properties"].items():
                assert "description" in spec
                assert len(spec["description"]) > 0
