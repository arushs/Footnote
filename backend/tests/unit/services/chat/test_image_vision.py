"""Tests for image vision support in the agent RAG."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_describe_image_with_vision_success():
    """Test successful image description with Claude vision."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This image shows a chart with revenue data.")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.services.chat.agent import _describe_image_with_vision

        # Fake image content
        image_bytes = b"fake_image_content"

        result = await _describe_image_with_vision(
            image_content=image_bytes,
            mime_type="image/png",
            file_name="revenue_chart.png",
        )

        assert result == "This image shows a chart with revenue data."
        mock_client.messages.create.assert_called_once()

        # Verify the call includes image data
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 1
        content = messages[0]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "image"
        assert content[0]["source"]["type"] == "base64"
        assert content[0]["source"]["media_type"] == "image/png"
        assert content[1]["type"] == "text"
        assert "revenue_chart.png" in content[1]["text"]


@pytest.mark.asyncio
async def test_describe_image_normalizes_jpg_mime_type():
    """Test that image/jpg is normalized to image/jpeg."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.services.chat.agent import _describe_image_with_vision

        await _describe_image_with_vision(
            image_content=b"fake",
            mime_type="image/jpg",  # Non-standard but common
            file_name="photo.jpg",
        )

        call_args = mock_client.messages.create.call_args
        content = call_args.kwargs["messages"][0]["content"]
        # Should be normalized to image/jpeg
        assert content[0]["source"]["media_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_describe_image_handles_api_error():
    """Test graceful handling of API errors."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_get_client.return_value = mock_client

        from app.services.chat.agent import _describe_image_with_vision

        result = await _describe_image_with_vision(
            image_content=b"fake",
            mime_type="image/png",
            file_name="test.png",
        )

        assert "[Image analysis failed:" in result
        assert "API error" in result


@pytest.mark.asyncio
async def test_describe_image_encodes_base64():
    """Test that image content is properly base64 encoded."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.services.chat.agent import _describe_image_with_vision

        test_content = b"test image bytes"
        expected_base64 = base64.b64encode(test_content).decode("utf-8")

        await _describe_image_with_vision(
            image_content=test_content,
            mime_type="image/png",
            file_name="test.png",
        )

        call_args = mock_client.messages.create.call_args
        content = call_args.kwargs["messages"][0]["content"]
        assert content[0]["source"]["data"] == expected_base64


@pytest.mark.asyncio
async def test_describe_image_includes_filename_in_prompt():
    """Test that the filename is included in the prompt for context."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.services.chat.agent import _describe_image_with_vision

        await _describe_image_with_vision(
            image_content=b"fake",
            mime_type="image/png",
            file_name="Q4_earnings_chart_2024.png",
        )

        call_args = mock_client.messages.create.call_args
        content = call_args.kwargs["messages"][0]["content"]
        text_prompt = content[1]["text"]
        assert "Q4_earnings_chart_2024.png" in text_prompt


@pytest.mark.asyncio
async def test_describe_image_uses_correct_model():
    """Test that the configured Claude model is used."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.services.chat.agent import _describe_image_with_vision

        await _describe_image_with_vision(
            image_content=b"fake",
            mime_type="image/png",
            file_name="test.png",
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-sonnet-4-5-20250929"


@pytest.mark.asyncio
async def test_describe_image_max_tokens_limited():
    """Test that max_tokens is set to a reasonable limit."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        from app.services.chat.agent import _describe_image_with_vision

        await _describe_image_with_vision(
            image_content=b"fake",
            mime_type="image/png",
            file_name="test.png",
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["max_tokens"] == 1000


@pytest.mark.asyncio
async def test_describe_image_handles_different_mime_types():
    """Test handling of various image MIME types."""
    with (
        patch("app.services.chat.agent.get_client") as mock_get_client,
        patch("app.services.chat.agent.settings") as mock_settings,
    ):
        mock_settings.claude_model = "claude-sonnet-4-5-20250929"

        from app.services.chat.agent import _describe_image_with_vision

        mime_types = [
            ("image/png", "image/png"),
            ("image/jpeg", "image/jpeg"),
            ("image/jpg", "image/jpeg"),  # Should be normalized
            ("image/gif", "image/gif"),
            ("image/webp", "image/webp"),
        ]

        for input_mime, expected_mime in mime_types:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Description")]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await _describe_image_with_vision(
                image_content=b"fake",
                mime_type=input_mime,
                file_name="test.img",
            )

            call_args = mock_client.messages.create.call_args
            content = call_args.kwargs["messages"][0]["content"]
            assert content[0]["source"]["media_type"] == expected_mime, f"Failed for {input_mime}"


@pytest.mark.asyncio
async def test_execute_tool_get_file_image():
    """Test that get_file tool handles images correctly."""
    import uuid
    from unittest.mock import MagicMock

    with (
        patch("app.services.chat.agent.get_user_session_for_folder") as mock_get_session,
        patch("app.services.chat.agent.DriveService") as mock_drive_class,
        patch("app.services.chat.agent.ExtractionService") as mock_extraction_class,
        patch("app.services.chat.agent._describe_image_with_vision") as mock_describe,
    ):
        # Setup mocks
        mock_session = MagicMock()
        mock_session.access_token = "test_token"
        mock_get_session.return_value = mock_session

        mock_drive = MagicMock()
        mock_drive.download_file = AsyncMock(return_value=b"image_bytes")
        mock_drive_class.return_value = mock_drive

        mock_extraction = MagicMock()
        mock_extraction.is_google_doc.return_value = False
        mock_extraction.is_pdf.return_value = False
        mock_extraction.is_image.return_value = True
        mock_extraction_class.return_value = mock_extraction

        mock_describe.return_value = "This is a chart showing quarterly revenue."

        # Create mock DB and file
        mock_db = MagicMock()
        mock_file = MagicMock()
        mock_file.id = uuid.uuid4()
        mock_file.folder_id = uuid.uuid4()
        mock_file.google_file_id = "google123"
        mock_file.file_name = "chart.png"
        mock_file.mime_type = "image/png"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_file
        mock_db.execute = AsyncMock(return_value=mock_result)

        folder_id = mock_file.folder_id
        indexed_chunks = []

        from app.services.chat.agent import execute_tool

        result = await execute_tool(
            "get_file",
            {"file_id": str(mock_file.id)},
            folder_id,
            mock_db,
            indexed_chunks,
        )

        # Verify image was processed
        assert "Image analysis" in result
        assert "chart.png" in result
        assert "quarterly revenue" in result

        # Verify indexed_chunks was updated
        assert len(indexed_chunks) == 1
        assert indexed_chunks[0]["file_name"] == "chart.png"
        assert indexed_chunks[0]["location"] == "Image analysis"

        # Verify vision function was called
        mock_describe.assert_called_once_with(b"image_bytes", "image/png", "chart.png")
