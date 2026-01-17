"""Tests for the agentic RAG service."""

import pytest
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent_rag import (
    format_location,
    build_google_drive_url,
    extract_citations_from_text,
    execute_tool,
    build_agent_system_prompt,
    DEFAULT_MAX_ITERATIONS,
)


class TestFormatLocation:
    """Tests for location formatting in agent module."""

    def test_format_location_with_page(self):
        """Should format page location."""
        location = {"page": 3}
        result = format_location(location)
        assert result == "Page 3"

    def test_format_location_with_headings(self):
        """Should format headings as breadcrumb."""
        location = {"headings": ["Intro", "Background"]}
        result = format_location(location)
        assert result == "Intro > Background"

    def test_format_location_empty(self):
        """Should return 'Document' for empty location."""
        result = format_location({})
        assert result == "Document"


class TestExtractCitationsFromText:
    """Tests for extracting [filename] citations."""

    def test_extract_matching_filename(self):
        """Should extract citations matching searched files."""
        text = "According to [report.pdf], the data shows..."
        searched_files = {
            "report.pdf": {
                "chunk_id": str(uuid.uuid4()),
                "file_id": uuid.uuid4(),
                "location": "Page 1",
                "excerpt": "Data shows...",
                "google_drive_url": "https://drive.google.com/file/d/abc/view",
            }
        }

        citations = extract_citations_from_text(text, searched_files)

        assert len(citations) == 1
        assert citations["1"]["file_name"] == "report.pdf"

    def test_extract_multiple_files(self):
        """Should extract multiple file citations."""
        text = "See [doc1.pdf] and also [doc2.pdf] for details."
        searched_files = {
            "doc1.pdf": {
                "chunk_id": "",
                "file_id": uuid.uuid4(),
                "location": "Page 1",
                "excerpt": "",
                "google_drive_url": "",
            },
            "doc2.pdf": {
                "chunk_id": "",
                "file_id": uuid.uuid4(),
                "location": "Page 2",
                "excerpt": "",
                "google_drive_url": "",
            },
        }

        citations = extract_citations_from_text(text, searched_files)

        assert len(citations) == 2

    def test_ignore_numeric_citations(self):
        """Should ignore numeric citations like [1]."""
        text = "This fact [1] is from [report.pdf]."
        searched_files = {
            "report.pdf": {
                "chunk_id": "",
                "file_id": uuid.uuid4(),
                "location": "",
                "excerpt": "",
                "google_drive_url": "",
            }
        }

        citations = extract_citations_from_text(text, searched_files)

        # Should only have the filename citation, not [1]
        assert len(citations) == 1

    def test_ignore_unknown_files(self):
        """Should ignore files not in searched_files."""
        text = "See [unknown.pdf] for details."
        searched_files = {
            "known.pdf": {
                "chunk_id": "",
                "file_id": uuid.uuid4(),
                "location": "",
                "excerpt": "",
                "google_drive_url": "",
            }
        }

        citations = extract_citations_from_text(text, searched_files)

        assert len(citations) == 0

    def test_empty_text(self):
        """Should return empty dict for empty text."""
        citations = extract_citations_from_text("", {})
        assert citations == {}


class TestExecuteTool:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_execute_search_folder_returns_json(self):
        """Search folder tool should return JSON response."""
        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        searched_files = {}

        # Only mock hybrid_search - it handles embed_query internally
        with patch("app.services.agent_rag.hybrid_search") as mock_search:
            mock_search.return_value = []

            result = await execute_tool(
                "search_folder",
                {"query": "test query"},
                folder_id,
                mock_db,
                searched_files,
            )

            parsed = json.loads(result)
            assert "chunks" in parsed
            assert isinstance(parsed["chunks"], list)

    @pytest.mark.asyncio
    async def test_execute_search_folder_does_not_call_embed_query_directly(self):
        """REGRESSION: execute_tool should NOT call embed_query directly.

        hybrid_search handles embedding internally. Calling embed_query twice
        caused timeout issues (the original bug this test prevents).
        """
        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        searched_files = {}

        with patch("app.services.agent_rag.hybrid_search") as mock_search:
            mock_search.return_value = []

            # Verify embed_query is not imported in agent_rag
            import app.services.agent_rag as agent_rag_module
            assert not hasattr(agent_rag_module, 'embed_query'), \
                "embed_query should not be imported in agent_rag - hybrid_search handles it"

            await execute_tool(
                "search_folder",
                {"query": "test query"},
                folder_id,
                mock_db,
                searched_files,
            )

            # Verify hybrid_search was called with the query string (not an embedding)
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args.kwargs
            assert call_kwargs["query"] == "test query"
            assert call_kwargs["folder_id"] == folder_id

    @pytest.mark.asyncio
    async def test_execute_search_folder_handles_search_errors(self):
        """Should return error JSON when hybrid_search fails."""
        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        searched_files = {}

        with patch("app.services.agent_rag.hybrid_search") as mock_search:
            mock_search.side_effect = Exception("Connection timeout")

            result = await execute_tool(
                "search_folder",
                {"query": "test query"},
                folder_id,
                mock_db,
                searched_files,
            )

            parsed = json.loads(result)
            assert "error" in parsed
            assert "Search failed" in parsed["error"]
            assert "Connection timeout" in parsed["error"]

    @pytest.mark.asyncio
    async def test_execute_search_folder_empty_query(self):
        """Search folder should return error for empty query."""
        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        searched_files = {}

        result = await execute_tool(
            "search_folder",
            {"query": ""},
            folder_id,
            mock_db,
            searched_files,
        )

        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_execute_get_file_invalid_id(self):
        """Get file should return error for invalid UUID."""
        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        searched_files = {}

        result = await execute_tool(
            "get_file",
            {"file_id": "not-a-uuid"},
            folder_id,
            mock_db,
            searched_files,
        )

        parsed = json.loads(result)
        assert "error" in parsed
        assert "Invalid" in parsed["error"]

    @pytest.mark.asyncio
    async def test_execute_get_file_not_found(self):
        """Get file should return error when file not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        folder_id = uuid.uuid4()
        searched_files = {}

        result = await execute_tool(
            "get_file",
            {"file_id": str(uuid.uuid4())},
            folder_id,
            mock_db,
            searched_files,
        )

        parsed = json.loads(result)
        assert "error" in parsed
        assert "not found" in parsed["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_get_file_success(self):
        """Get file should return file content when found."""
        mock_db = AsyncMock()
        mock_file = MagicMock()
        mock_file.id = uuid.uuid4()
        mock_file.file_name = "test.pdf"
        mock_file.file_preview = "This is the content..."
        mock_file.mime_type = "application/pdf"
        mock_file.google_file_id = "gid123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_file
        mock_db.execute = AsyncMock(return_value=mock_result)

        folder_id = uuid.uuid4()
        searched_files = {}

        # Mock get_user_session_for_folder, DriveService, and ExtractionService
        mock_session = MagicMock()
        mock_session.access_token = "test_token"

        mock_document = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "This is the extracted content..."
        mock_document.blocks = [mock_block]

        with patch("app.services.agent_rag.get_user_session_for_folder") as mock_get_session, \
             patch("app.services.agent_rag.DriveService") as mock_drive_class, \
             patch("app.services.agent_rag.ExtractionService") as mock_extraction_class:

            mock_get_session.return_value = mock_session

            mock_drive = MagicMock()
            mock_drive.download_file = AsyncMock(return_value=b"pdf content")
            mock_drive_class.return_value = mock_drive

            mock_extraction = MagicMock()
            mock_extraction.is_google_doc.return_value = False
            mock_extraction.is_pdf.return_value = True
            mock_extraction.extract_pdf = AsyncMock(return_value=mock_document)
            mock_extraction_class.return_value = mock_extraction

            result = await execute_tool(
                "get_file",
                {"file_id": str(uuid.uuid4())},
                folder_id,
                mock_db,
                searched_files,
            )

            parsed = json.loads(result)
            assert parsed["file_name"] == "test.pdf"
            assert "content" in parsed
            assert parsed["source"] == "google_drive"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Unknown tool should return error."""
        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        searched_files = {}

        result = await execute_tool(
            "unknown_tool",
            {},
            folder_id,
            mock_db,
            searched_files,
        )

        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]


class TestConstants:
    """Tests for module constants."""

    def test_max_iterations_is_reasonable(self):
        """Max iterations should be reasonable to avoid infinite loops."""
        assert DEFAULT_MAX_ITERATIONS > 0
        assert DEFAULT_MAX_ITERATIONS <= 15


class TestBuildAgentSystemPrompt:
    """Tests for dynamic system prompt generation."""

    def test_includes_folder_name(self):
        """System prompt should include folder name."""
        prompt = build_agent_system_prompt(
            folder_name="My Documents",
            files_indexed=10,
            files_total=15,
            max_iterations=10,
        )
        assert "My Documents" in prompt

    def test_includes_file_counts(self):
        """System prompt should include file count information."""
        prompt = build_agent_system_prompt(
            folder_name="Test Folder",
            files_indexed=5,
            files_total=10,
            max_iterations=10,
        )
        assert "5/10" in prompt or ("5" in prompt and "10" in prompt)

    def test_includes_iteration_limit(self):
        """System prompt should mention iteration limit."""
        prompt = build_agent_system_prompt(
            folder_name="Folder",
            files_indexed=1,
            files_total=1,
            max_iterations=8,
        )
        assert "8" in prompt

    def test_mentions_available_tools(self):
        """System prompt should mention available tools."""
        prompt = build_agent_system_prompt(
            folder_name="Folder",
            files_indexed=1,
            files_total=1,
            max_iterations=10,
        )
        prompt_lower = prompt.lower()
        assert "search_folder" in prompt_lower
        assert "get_file" in prompt_lower
        assert "get_file_chunks" in prompt_lower

    def test_does_not_mention_rewrite_query(self):
        """System prompt should NOT mention removed rewrite_query tool."""
        prompt = build_agent_system_prompt(
            folder_name="Folder",
            files_indexed=1,
            files_total=1,
            max_iterations=10,
        )
        assert "rewrite_query" not in prompt.lower()

    def test_includes_search_quality_guidance(self):
        """System prompt should include RRF score guidance."""
        prompt = build_agent_system_prompt(
            folder_name="Folder",
            files_indexed=1,
            files_total=1,
            max_iterations=10,
        )
        assert "rrf" in prompt.lower() or "score" in prompt.lower()


class TestAgenticRAGFlow:
    """Integration tests for the agentic RAG flow."""

    @pytest.mark.asyncio
    async def test_agentic_rag_emits_status(self):
        """Agentic RAG should emit agent_status events."""
        from app.services.agent_rag import agentic_rag

        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        conversation = MagicMock()
        conversation.id = uuid.uuid4()

        # Mock DB queries
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        with patch("app.services.agent_rag.get_client") as mock_get_client:
            mock_client = MagicMock()

            # Mock a response that doesn't use tools
            mock_response = MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [MagicMock(text="Here is my answer", type="text")]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            chunks = []
            async for chunk in agentic_rag(
                mock_db, folder_id, conversation, "test question"
            ):
                chunks.append(chunk)

            # Should have status and token chunks
            assert any("agent_status" in c for c in chunks)
            assert any("done" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_agentic_rag_handles_tool_use(self):
        """Agentic RAG should handle tool use responses."""
        from app.services.agent_rag import agentic_rag

        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        conversation = MagicMock()
        conversation.id = uuid.uuid4()

        # Mock DB queries
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        # Only mock hybrid_search - embed_query is handled internally
        with patch("app.services.agent_rag.get_client") as mock_get_client, \
             patch("app.services.agent_rag.hybrid_search") as mock_search:

            mock_search.return_value = []

            mock_client = MagicMock()

            # First response uses a tool
            tool_use_response = MagicMock()
            tool_use_response.stop_reason = "tool_use"
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.name = "search_folder"
            tool_block.input = {"query": "test"}
            tool_block.id = "tool_123"
            tool_use_response.content = [tool_block]

            # Second response is final
            final_response = MagicMock()
            final_response.stop_reason = "end_turn"
            text_block = MagicMock()
            text_block.type = "text"
            text_block.text = "Based on my search, here is the answer."
            final_response.content = [text_block]

            mock_client.messages.create = AsyncMock(
                side_effect=[tool_use_response, final_response]
            )
            mock_get_client.return_value = mock_client

            chunks = []
            async for chunk in agentic_rag(
                mock_db, folder_id, conversation, "test question"
            ):
                chunks.append(chunk)

            # Should have multiple iterations
            assert mock_client.messages.create.call_count == 2
            assert any("done" in c for c in chunks)
