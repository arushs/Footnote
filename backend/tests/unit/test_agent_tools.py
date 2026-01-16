"""Tests for agent tool definitions."""

import pytest

from app.services.agent_tools import (
    SEARCH_FOLDER_TOOL,
    REWRITE_QUERY_TOOL,
    GET_FILE_TOOL,
    ALL_TOOLS,
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


class TestRewriteQueryTool:
    """Tests for the rewrite_query tool definition."""

    def test_tool_has_required_fields(self):
        """Tool should have name, description, and input_schema."""
        assert "name" in REWRITE_QUERY_TOOL
        assert "description" in REWRITE_QUERY_TOOL
        assert "input_schema" in REWRITE_QUERY_TOOL

    def test_tool_name_is_rewrite_query(self):
        """Tool name should be rewrite_query."""
        assert REWRITE_QUERY_TOOL["name"] == "rewrite_query"

    def test_tool_requires_original_query(self):
        """Tool should require original_query parameter."""
        schema = REWRITE_QUERY_TOOL["input_schema"]
        assert "original_query" in schema["properties"]
        assert "original_query" in schema["required"]

    def test_tool_requires_feedback(self):
        """Tool should require feedback parameter."""
        schema = REWRITE_QUERY_TOOL["input_schema"]
        assert "feedback" in schema["properties"]
        assert "feedback" in schema["required"]

    def test_both_parameters_are_strings(self):
        """Both parameters should be strings."""
        schema = REWRITE_QUERY_TOOL["input_schema"]
        assert schema["properties"]["original_query"]["type"] == "string"
        assert schema["properties"]["feedback"]["type"] == "string"


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

    def test_description_mentions_uuid(self):
        """Description should mention UUID."""
        desc = GET_FILE_TOOL["description"].lower()
        assert "uuid" in desc


class TestAllTools:
    """Tests for the ALL_TOOLS list."""

    def test_all_tools_contains_three_tools(self):
        """ALL_TOOLS should contain exactly 3 tools."""
        assert len(ALL_TOOLS) == 3

    def test_all_tools_contains_search_folder(self):
        """ALL_TOOLS should include search_folder."""
        tool_names = [t["name"] for t in ALL_TOOLS]
        assert "search_folder" in tool_names

    def test_all_tools_contains_rewrite_query(self):
        """ALL_TOOLS should include rewrite_query."""
        tool_names = [t["name"] for t in ALL_TOOLS]
        assert "rewrite_query" in tool_names

    def test_all_tools_contains_get_file(self):
        """ALL_TOOLS should include get_file."""
        tool_names = [t["name"] for t in ALL_TOOLS]
        assert "get_file" in tool_names

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
            for param, spec in tool["input_schema"]["properties"].items():
                assert "description" in spec
                assert len(spec["description"]) > 0
