"""Tests for contextual retrieval functionality in the worker."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.chunking import DocumentChunk


@pytest.mark.asyncio
async def test_generate_chunk_contexts_success():
    """Test successful parallel context generation."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        # Setup mock client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="From the introduction section.")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Test chunk content", location={}, chunk_index=0)]
        # Document must be >500 chars to trigger context generation
        long_document = "A" * 600

        results = await _generate_chunk_contexts("test.pdf", long_document, chunks)

        assert len(results) == 1
        assert "From the introduction section." in results[0]
        assert "Test chunk content" in results[0]
        # Verify context is prepended with newlines
        assert results[0].startswith("From the introduction section.\n\n")


@pytest.mark.asyncio
async def test_generate_chunk_contexts_multiple_chunks():
    """Test context generation for multiple chunks in parallel."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        # Return different contexts for each call
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"Context for chunk {call_count}.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [
            DocumentChunk(text="First chunk", location={}, chunk_index=0),
            DocumentChunk(text="Second chunk", location={}, chunk_index=1),
            DocumentChunk(text="Third chunk", location={}, chunk_index=2),
        ]
        long_document = "A" * 600

        results = await _generate_chunk_contexts("test.pdf", long_document, chunks)

        assert len(results) == 3
        # Each chunk should have context prepended
        for i, result in enumerate(results):
            assert f"chunk {i + 1}" in result.lower() or chunks[i].text in result


@pytest.mark.asyncio
async def test_short_document_skips_context():
    """Test that short documents skip context generation entirely."""
    from app.worker import _generate_chunk_contexts

    chunks = [DocumentChunk(text="Short chunk", location={}, chunk_index=0)]
    short_document = "This is a short document"  # < 500 chars

    results = await _generate_chunk_contexts("test.pdf", short_document, chunks)

    # Should return original text unchanged
    assert results == ["Short chunk"]


@pytest.mark.asyncio
async def test_api_failure_falls_back_to_original():
    """Test graceful fallback when API fails."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Original text", location={}, chunk_index=0)]
        long_document = "A" * 600

        results = await _generate_chunk_contexts("test.pdf", long_document, chunks)

        # Should fall back to original chunk text
        assert results == ["Original text"]


@pytest.mark.asyncio
async def test_partial_failure_preserves_successful_contexts():
    """Test that partial API failures don't affect successful context generation."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("API error for second chunk")
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"Context {call_count}.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [
            DocumentChunk(text="First", location={}, chunk_index=0),
            DocumentChunk(text="Second", location={}, chunk_index=1),
            DocumentChunk(text="Third", location={}, chunk_index=2),
        ]
        long_document = "A" * 600

        results = await _generate_chunk_contexts("test.pdf", long_document, chunks)

        assert len(results) == 3
        # First and third should have context
        assert "Context" in results[0]
        assert "First" in results[0]
        # Second should fall back to original
        assert results[1] == "Second"
        # Third should have context
        assert "Context" in results[2]
        assert "Third" in results[2]


@pytest.mark.asyncio
async def test_long_document_truncation():
    """Test that very long documents are truncated."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()

        captured_content = None

        async def mock_create(**kwargs):
            nonlocal captured_content
            captured_content = kwargs["messages"][0]["content"]
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        # Create a document longer than 6000 chars
        very_long_document = "A" * 10000

        await _generate_chunk_contexts("test.pdf", very_long_document, chunks)

        # Document should be truncated in the prompt
        assert captured_content is not None
        assert "[...truncated...]" in captured_content
        # Should not contain all 10000 A's
        assert len(captured_content) < 10000


@pytest.mark.asyncio
async def test_generate_single_context_success():
    """Test the single context generation function."""
    with patch("app.worker.settings") as mock_settings:
        mock_settings.claude_fast_model = "claude-3-haiku-20240307"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="  Generated context.  ")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from app.worker import _generate_single_context

        result = await _generate_single_context(
            client=mock_client,
            file_name="doc.pdf",
            document_excerpt="Document content here",
            chunk_text="Chunk to contextualize",
        )

        # Should strip whitespace
        assert result == "Generated context."


@pytest.mark.asyncio
async def test_empty_chunks_list():
    """Test handling of empty chunks list."""
    from app.worker import _generate_chunk_contexts

    results = await _generate_chunk_contexts("test.pdf", "A" * 600, [])

    assert results == []


@pytest.mark.asyncio
async def test_file_name_included_in_prompt():
    """Test that file name is included in the context prompt."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()

        captured_content = None

        async def mock_create(**kwargs):
            nonlocal captured_content
            captured_content = kwargs["messages"][0]["content"]
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]

        await _generate_chunk_contexts(
            "quarterly_report_2024.pdf", "A" * 600, chunks
        )

        assert captured_content is not None
        assert "quarterly_report_2024.pdf" in captured_content


@pytest.mark.asyncio
async def test_chunk_text_included_in_prompt():
    """Test that the chunk text is included in the context prompt."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()

        captured_content = None

        async def mock_create(**kwargs):
            nonlocal captured_content
            captured_content = kwargs["messages"][0]["content"]
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunk_text = "Revenue grew by 15% in Q4 compared to the previous quarter."
        chunks = [DocumentChunk(text=chunk_text, location={}, chunk_index=0)]

        await _generate_chunk_contexts("report.pdf", "A" * 600, chunks)

        assert captured_content is not None
        assert chunk_text in captured_content


@pytest.mark.asyncio
async def test_document_excerpt_included_in_prompt():
    """Test that document excerpt is included in the context prompt."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()

        captured_content = None

        async def mock_create(**kwargs):
            nonlocal captured_content
            captured_content = kwargs["messages"][0]["content"]
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        document_text = "This is the start of our financial report. " * 50  # ~2500 chars
        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]

        await _generate_chunk_contexts("report.pdf", document_text, chunks)

        assert captured_content is not None
        assert "This is the start of our financial report" in captured_content


@pytest.mark.asyncio
async def test_context_format_with_newlines():
    """Test that context is prepended with proper formatting (two newlines)."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is context about the chunk.")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        original_text = "Original chunk content here."
        chunks = [DocumentChunk(text=original_text, location={}, chunk_index=0)]

        results = await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        # Format should be: context + "\n\n" + original_text
        expected = "This is context about the chunk.\n\n" + original_text
        assert results[0] == expected


@pytest.mark.asyncio
async def test_concurrent_limit_respected():
    """Test that max_concurrent limit is respected."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()

        concurrent_calls = 0
        max_concurrent_observed = 0

        async def mock_create(**kwargs):
            nonlocal concurrent_calls, max_concurrent_observed
            concurrent_calls += 1
            max_concurrent_observed = max(max_concurrent_observed, concurrent_calls)
            await asyncio.sleep(0.01)  # Simulate API latency
            concurrent_calls -= 1
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        # Create 10 chunks to process
        chunks = [
            DocumentChunk(text=f"Chunk {i}", location={}, chunk_index=i)
            for i in range(10)
        ]

        # Use max_concurrent=3
        await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks, max_concurrent=3)

        # Should never exceed 3 concurrent calls
        assert max_concurrent_observed <= 3


@pytest.mark.asyncio
async def test_uses_correct_model():
    """Test that the correct model (claude_fast_model) is used."""
    with patch("app.worker.get_anthropic_client") as mock_get_client, \
         patch("app.worker.settings") as mock_settings:
        mock_settings.claude_fast_model = "claude-3-haiku-20240307"

        mock_client = MagicMock()
        captured_model = None

        async def mock_create(**kwargs):
            nonlocal captured_model
            captured_model = kwargs.get("model")
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        assert captured_model == "claude-3-haiku-20240307"


@pytest.mark.asyncio
async def test_temperature_is_zero():
    """Test that temperature is set to 0 for deterministic output."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        captured_temperature = None

        async def mock_create(**kwargs):
            nonlocal captured_temperature
            captured_temperature = kwargs.get("temperature")
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        assert captured_temperature == 0.0


@pytest.mark.asyncio
async def test_max_tokens_is_limited():
    """Test that max_tokens is limited to prevent excessive output."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        captured_max_tokens = None

        async def mock_create(**kwargs):
            nonlocal captured_max_tokens
            captured_max_tokens = kwargs.get("max_tokens")
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        # Should be a reasonable limit (100 tokens as per implementation)
        assert captured_max_tokens == 100


@pytest.mark.asyncio
async def test_boundary_document_length_499():
    """Test document with exactly 499 chars skips context."""
    from app.worker import _generate_chunk_contexts

    chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
    document = "A" * 499  # Just under the threshold

    results = await _generate_chunk_contexts("doc.pdf", document, chunks)

    assert results == ["Chunk"]  # No context added


@pytest.mark.asyncio
async def test_boundary_document_length_500():
    """Test document with exactly 500 chars generates context."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Context.")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        document = "A" * 500  # Exactly at threshold

        results = await _generate_chunk_contexts("doc.pdf", document, chunks)

        # Should have context since 500 >= 500
        assert "Context." in results[0]


@pytest.mark.asyncio
async def test_boundary_document_length_6000():
    """Test document with exactly 6000 chars is not truncated."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        captured_content = None

        async def mock_create(**kwargs):
            nonlocal captured_content
            captured_content = kwargs["messages"][0]["content"]
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        document = "A" * 6000  # Exactly at truncation limit

        await _generate_chunk_contexts("doc.pdf", document, chunks)

        # Should NOT contain truncation marker
        assert "[...truncated...]" not in captured_content


@pytest.mark.asyncio
async def test_boundary_document_length_6001():
    """Test document with 6001 chars is truncated."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        captured_content = None

        async def mock_create(**kwargs):
            nonlocal captured_content
            captured_content = kwargs["messages"][0]["content"]
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        document = "A" * 6001  # Just over truncation limit

        await _generate_chunk_contexts("doc.pdf", document, chunks)

        # Should contain truncation marker
        assert "[...truncated...]" in captured_content


@pytest.mark.asyncio
async def test_preserves_chunk_order():
    """Test that chunk order is preserved in results."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        call_order = []

        async def mock_create(**kwargs):
            content = kwargs["messages"][0]["content"]
            # Extract chunk number from the prompt
            for i in range(5):
                if f"Chunk {i}" in content:
                    call_order.append(i)
                    break
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"Context for chunk.")]
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [
            DocumentChunk(text=f"Chunk {i} content", location={}, chunk_index=i)
            for i in range(5)
        ]

        results = await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        # Results should maintain chunk order
        assert len(results) == 5
        for i, result in enumerate(results):
            assert f"Chunk {i} content" in result


@pytest.mark.asyncio
async def test_handles_unicode_content():
    """Test handling of unicode characters in document and chunks."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Context with émojis 🎉")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        unicode_text = "日本語テキスト with émojis 🎉 and symbols €£¥"
        chunks = [DocumentChunk(text=unicode_text, location={}, chunk_index=0)]
        document = "A" * 500 + " 日本語ドキュメント 📄"

        results = await _generate_chunk_contexts("unicode_doc.pdf", document, chunks)

        # Should handle unicode without errors
        assert len(results) == 1
        assert unicode_text in results[0]
        assert "Context with émojis 🎉" in results[0]


@pytest.mark.asyncio
async def test_handles_empty_context_response():
    """Test handling when LLM returns empty string."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="   ")]  # Whitespace only
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Original", location={}, chunk_index=0)]

        results = await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        # Empty context after strip should fall back to original
        # Since the stripped context is empty string, it should return original
        assert results[0] == "Original"
