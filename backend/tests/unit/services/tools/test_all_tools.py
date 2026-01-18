"""Tests for ALL_TOOLS list and schema validity."""

from app.services.tools import ALL_TOOLS


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
