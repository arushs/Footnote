"""Tests for contextual retrieval functionality with prompt caching."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.file.chunking import DocumentChunk


def extract_text_from_content(content):
    """Extract text from content which can be string or list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content)
    return ""


@pytest.mark.asyncio
async def test_generate_chunk_contexts_success():
    """Test successful context generation with prompt caching."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="From the introduction section.")]
        mock_response.usage = MagicMock()
        mock_response.usage.cache_creation_input_tokens = 100
        mock_response.usage.cache_read_input_tokens = 0
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Test chunk content", location={}, chunk_index=0)]
        long_document = "A" * 600

        results = await _generate_chunk_contexts("test.pdf", long_document, chunks)

        assert len(results) == 1
        assert "From the introduction section." in results[0]
        assert "Test chunk content" in results[0]
        assert results[0].startswith("From the introduction section.\n\n")


@pytest.mark.asyncio
async def test_generate_chunk_contexts_multiple_chunks():
    """Test context generation for multiple chunks with prompt caching."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"Context for chunk {call_count}.")]
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 100 if call_count == 1 else 0
            mock_response.usage.cache_read_input_tokens = 0 if call_count == 1 else 100
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
        for i, result in enumerate(results):
            assert f"chunk {i + 1}" in result.lower() or chunks[i].text in result


@pytest.mark.asyncio
async def test_short_document_skips_context():
    """Test that short documents skip context generation entirely."""
    from app.worker import _generate_chunk_contexts

    chunks = [DocumentChunk(text="Short chunk", location={}, chunk_index=0)]
    short_document = "This is a short document"

    results = await _generate_chunk_contexts("test.pdf", short_document, chunks)

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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
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
        assert "Context" in results[0]
        assert "First" in results[0]
        assert results[1] == "Second"
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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        very_long_document = "A" * 10000

        await _generate_chunk_contexts("test.pdf", very_long_document, chunks)

        assert captured_content is not None
        full_text = extract_text_from_content(captured_content)
        assert "[...truncated...]" in full_text
        assert len(full_text) < 10000


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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]

        await _generate_chunk_contexts("quarterly_report_2024.pdf", "A" * 600, chunks)

        assert captured_content is not None
        full_text = extract_text_from_content(captured_content)
        assert "quarterly_report_2024.pdf" in full_text


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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunk_text = "Revenue grew by 15% in Q4 compared to the previous quarter."
        chunks = [DocumentChunk(text=chunk_text, location={}, chunk_index=0)]

        await _generate_chunk_contexts("report.pdf", "A" * 600, chunks)

        assert captured_content is not None
        full_text = extract_text_from_content(captured_content)
        assert chunk_text in full_text


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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        document_text = "This is the start of our financial report. " * 50
        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]

        await _generate_chunk_contexts("report.pdf", document_text, chunks)

        assert captured_content is not None
        full_text = extract_text_from_content(captured_content)
        assert "This is the start of our financial report" in full_text


@pytest.mark.asyncio
async def test_context_format_with_newlines():
    """Test that context is prepended with proper formatting (two newlines)."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is context about the chunk.")]
        mock_response.usage = MagicMock()
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        original_text = "Original chunk content here."
        chunks = [DocumentChunk(text=original_text, location={}, chunk_index=0)]

        results = await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        expected = "This is context about the chunk.\n\n" + original_text
        assert results[0] == expected


@pytest.mark.asyncio
async def test_uses_correct_model():
    """Test that the correct model (claude_fast_model) is used."""
    with (
        patch("app.worker.get_anthropic_client") as mock_get_client,
        patch("app.worker.settings") as mock_settings,
    ):
        mock_settings.claude_fast_model = "claude-3-haiku-20240307"

        mock_client = MagicMock()
        captured_model = None

        async def mock_create(**kwargs):
            nonlocal captured_model
            captured_model = kwargs.get("model")
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        assert captured_max_tokens == 100


@pytest.mark.asyncio
async def test_boundary_document_length_499():
    """Test document with exactly 499 chars skips context."""
    from app.worker import _generate_chunk_contexts

    chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
    document = "A" * 499

    results = await _generate_chunk_contexts("doc.pdf", document, chunks)

    assert results == ["Chunk"]


@pytest.mark.asyncio
async def test_boundary_document_length_500():
    """Test document with exactly 500 chars generates context."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Context.")]
        mock_response.usage = MagicMock()
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        document = "A" * 500

        results = await _generate_chunk_contexts("doc.pdf", document, chunks)

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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        document = "A" * 6000

        await _generate_chunk_contexts("doc.pdf", document, chunks)

        full_text = extract_text_from_content(captured_content)
        assert "[...truncated...]" not in full_text


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
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        document = "A" * 6001

        await _generate_chunk_contexts("doc.pdf", document, chunks)

        full_text = extract_text_from_content(captured_content)
        assert "[...truncated...]" in full_text


@pytest.mark.asyncio
async def test_preserves_chunk_order():
    """Test that chunk order is preserved in results."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        call_order = []

        async def mock_create(**kwargs):
            content = kwargs["messages"][0]["content"]
            full_text = extract_text_from_content(content)
            for i in range(5):
                if f"Chunk {i}" in full_text:
                    call_order.append(i)
                    break
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context for chunk.")]
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 0
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [
            DocumentChunk(text=f"Chunk {i} content", location={}, chunk_index=i) for i in range(5)
        ]

        results = await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert f"Chunk {i} content" in result


@pytest.mark.asyncio
async def test_handles_unicode_content():
    """Test handling of unicode characters in document and chunks."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Context with emojis")]
        mock_response.usage = MagicMock()
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        unicode_text = "Japanese text with emojis and symbols"
        chunks = [DocumentChunk(text=unicode_text, location={}, chunk_index=0)]
        document = "A" * 500 + " Japanese document"

        results = await _generate_chunk_contexts("unicode_doc.pdf", document, chunks)

        assert len(results) == 1
        assert unicode_text in results[0]
        assert "Context with emojis" in results[0]


@pytest.mark.asyncio
async def test_handles_empty_context_response():
    """Test handling when LLM returns empty string."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="   ")]
        mock_response.usage = MagicMock()
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Original", location={}, chunk_index=0)]

        results = await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        # Empty context after strip should fall back to original
        assert results[0] == "Original"


@pytest.mark.asyncio
async def test_cache_control_is_set():
    """Test that cache_control is properly set on the document block."""
    with patch("app.worker.get_anthropic_client") as mock_get_client:
        mock_client = MagicMock()
        captured_content = None

        async def mock_create(**kwargs):
            nonlocal captured_content
            captured_content = kwargs["messages"][0]["content"]
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Context.")]
            mock_response.usage = MagicMock()
            mock_response.usage.cache_creation_input_tokens = 100
            mock_response.usage.cache_read_input_tokens = 0
            return mock_response

        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        from app.worker import _generate_chunk_contexts

        chunks = [DocumentChunk(text="Chunk", location={}, chunk_index=0)]
        await _generate_chunk_contexts("doc.pdf", "A" * 600, chunks)

        # Content should be a list with cache_control on the first block
        assert isinstance(captured_content, list)
        assert len(captured_content) == 2
        assert captured_content[0].get("cache_control") == {"type": "ephemeral"}
        assert "cache_control" not in captured_content[1]
