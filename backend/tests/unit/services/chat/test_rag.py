"""Tests for the standard RAG chat service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat.rag import (
    CONTEXT_TOP_K,
    STANDARD_SYSTEM_PROMPT,
    build_context,
    build_google_drive_url,
    extract_citation_numbers,
    format_location,
)


class TestFormatLocation:
    """Tests for location formatting."""

    def test_format_location_with_page(self):
        """Should format page location."""
        location = {"page": 5}
        result = format_location(location)
        assert result == "Page 5"

    def test_format_location_with_headings(self):
        """Should format headings as breadcrumb."""
        location = {"headings": ["Chapter 1", "Section 2"]}
        result = format_location(location)
        assert result == "Chapter 1 > Section 2"

    def test_format_location_with_heading_path(self):
        """Should format heading_path directly."""
        location = {"heading_path": "Introduction > Overview"}
        result = format_location(location)
        assert result == "Introduction > Overview"

    def test_format_location_with_index(self):
        """Should format index as section number."""
        location = {"index": 2}
        result = format_location(location)
        assert result == "Section 3"

    def test_format_location_empty(self):
        """Should return 'Document' for empty location."""
        result = format_location({})
        assert result == "Document"

    def test_format_location_none(self):
        """Should return 'Document' for None location."""
        result = format_location(None)
        assert result == "Document"


class TestBuildGoogleDriveUrl:
    """Tests for Google Drive URL building."""

    def test_build_url_with_file_id(self):
        """Should build valid Drive URL."""
        url = build_google_drive_url("abc123xyz")
        assert url == "https://drive.google.com/file/d/abc123xyz/view"

    def test_build_url_with_different_id(self):
        """Should work with different file IDs."""
        url = build_google_drive_url("1A2B3C4D5E")
        assert url == "https://drive.google.com/file/d/1A2B3C4D5E/view"


class TestBuildContext:
    """Tests for context building from chunks."""

    def test_build_context_single_chunk(self):
        """Should format single chunk correctly."""
        chunk = MagicMock()
        chunk.file_name = "test.pdf"
        chunk.location = {"page": 1}
        chunk.chunk_text = "This is test content."

        context = build_context([chunk])

        assert "[1]" in context
        assert "test.pdf" in context
        assert "Page 1" in context
        assert "This is test content." in context

    def test_build_context_multiple_chunks(self):
        """Should format multiple chunks with separators."""
        chunks = []
        for i in range(3):
            chunk = MagicMock()
            chunk.file_name = f"file{i + 1}.pdf"
            chunk.location = {"page": i + 1}
            chunk.chunk_text = f"Content from chunk {i + 1}."
            chunks.append(chunk)

        context = build_context(chunks)

        assert "[1]" in context
        assert "[2]" in context
        assert "[3]" in context
        assert "---" in context  # Separator
        assert "file1.pdf" in context
        assert "file2.pdf" in context
        assert "file3.pdf" in context

    def test_build_context_empty_list(self):
        """Should return empty string for empty list."""
        context = build_context([])
        assert context == ""


class TestExtractCitationNumbers:
    """Tests for citation extraction from text."""

    def test_extract_single_citation(self):
        """Should extract single citation number."""
        text = "This is a fact [1]."
        citations = extract_citation_numbers(text)
        assert citations == {1}

    def test_extract_multiple_citations(self):
        """Should extract multiple citation numbers."""
        text = "Fact one [1], fact two [2], and fact three [3]."
        citations = extract_citation_numbers(text)
        assert citations == {1, 2, 3}

    def test_extract_duplicate_citations(self):
        """Should return unique citation numbers."""
        text = "Fact [1] is related to [1] again and [2]."
        citations = extract_citation_numbers(text)
        assert citations == {1, 2}

    def test_extract_no_citations(self):
        """Should return empty set when no citations."""
        text = "This text has no citations."
        citations = extract_citation_numbers(text)
        assert citations == set()

    def test_extract_double_digit_citations(self):
        """Should handle double-digit citation numbers."""
        text = "Source [10] and source [15]."
        citations = extract_citation_numbers(text)
        assert citations == {10, 15}

    def test_extract_ignores_non_numeric_brackets(self):
        """Should ignore non-numeric content in brackets."""
        text = "This [note] is not a citation but [1] is."
        citations = extract_citation_numbers(text)
        assert citations == {1}


class TestConstants:
    """Tests for module constants."""

    def test_context_top_k_is_reasonable(self):
        """Context top k should be reasonable for LLM."""
        assert CONTEXT_TOP_K > 0
        assert CONTEXT_TOP_K <= 20  # Don't want too much context

    def test_system_prompt_contains_instructions(self):
        """System prompt should contain key instructions."""
        assert "citation" in STANDARD_SYSTEM_PROMPT.lower()
        assert "source" in STANDARD_SYSTEM_PROMPT.lower()
        assert "[" in STANDARD_SYSTEM_PROMPT  # Citation format


class TestStandardRAGFlow:
    """Integration tests for the standard RAG flow."""

    @pytest.mark.asyncio
    async def test_standard_rag_yields_tokens(self):
        """Standard RAG should yield SSE-formatted tokens."""
        from app.services.chat.rag import standard_rag

        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        user_id = uuid.uuid4()
        conversation = MagicMock()
        conversation.id = uuid.uuid4()

        # Mock DB queries
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        # Mock hybrid search
        with patch("app.services.chat.rag.hybrid_retrieve_and_rerank") as mock_search:
            mock_search.return_value = []

            # Mock Anthropic client
            with patch("app.services.chat.rag.get_client") as mock_get_client:
                mock_client = MagicMock()

                class MockUsage:
                    input_tokens = 100
                    output_tokens = 50

                class MockFinalMessage:
                    usage = MockUsage()

                class MockStream:
                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        pass

                    @property
                    def text_stream(self):
                        async def gen():
                            yield "Test"
                            yield " response"

                        return gen()

                    async def get_final_message(self):
                        return MockFinalMessage()

                mock_client.messages.stream.return_value = MockStream()
                mock_get_client.return_value = mock_client

                with patch("app.services.chat.rag.track_llm_generation"):
                    # Collect all yielded chunks
                    chunks = []
                    async for chunk in standard_rag(
                        mock_db, folder_id, user_id, conversation, "test question"
                    ):
                        chunks.append(chunk)

                    # Should have token chunks and done message
                    assert len(chunks) > 0
                    assert any("token" in c for c in chunks)
                    assert any("done" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_standard_rag_stores_messages(self):
        """Standard RAG should store user and assistant messages."""
        from app.services.chat.rag import standard_rag

        mock_db = AsyncMock()
        folder_id = uuid.uuid4()
        user_id = uuid.uuid4()
        conversation = MagicMock()
        conversation.id = uuid.uuid4()

        # Mock DB queries
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        with patch("app.services.chat.rag.hybrid_retrieve_and_rerank") as mock_search:
            mock_search.return_value = []

            with patch("app.services.chat.rag.get_client") as mock_get_client:
                mock_client = MagicMock()

                class MockUsage:
                    input_tokens = 100
                    output_tokens = 50

                class MockFinalMessage:
                    usage = MockUsage()

                class MockStream:
                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        pass

                    @property
                    def text_stream(self):
                        async def gen():
                            yield "Response"

                        return gen()

                    async def get_final_message(self):
                        return MockFinalMessage()

                mock_client.messages.stream.return_value = MockStream()
                mock_get_client.return_value = mock_client

                with patch("app.services.chat.rag.track_llm_generation"):
                    async for _ in standard_rag(
                        mock_db, folder_id, user_id, conversation, "test question"
                    ):
                        pass

                    # Should have called db.add twice (user + assistant)
                    assert mock_db.add.call_count == 2
