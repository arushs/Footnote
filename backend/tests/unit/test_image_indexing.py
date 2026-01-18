"""Unit tests for image indexing functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.file.extraction import ExtractionService, ImageExtractor, MAX_IMAGE_SIZE_BYTES


class TestExtractionServiceImageMethods:
    """Tests for ExtractionService image-related methods."""

    def test_is_image_with_supported_types(self):
        """Test is_image returns True for all image types."""
        service = ExtractionService()
        assert service.is_image("image/jpeg") is True
        assert service.is_image("image/png") is True
        assert service.is_image("image/gif") is True
        assert service.is_image("image/webp") is True
        assert service.is_image("image/bmp") is True
        assert service.is_image("image/tiff") is True
        assert service.is_image("image/svg+xml") is True

    def test_is_image_with_unknown_image_type(self):
        """Test is_image returns True for unknown image/* types."""
        service = ExtractionService()
        assert service.is_image("image/unknown") is True
        assert service.is_image("image/x-custom") is True

    def test_is_image_with_non_image_types(self):
        """Test is_image returns False for non-image types."""
        service = ExtractionService()
        assert service.is_image("application/pdf") is False
        assert service.is_image("text/plain") is False
        assert service.is_image("application/vnd.google-apps.document") is False

    def test_is_vision_supported_with_supported_types(self):
        """Test is_vision_supported returns True for Claude Vision supported types."""
        service = ExtractionService()
        assert service.is_vision_supported("image/jpeg") is True
        assert service.is_vision_supported("image/png") is True
        assert service.is_vision_supported("image/gif") is True
        assert service.is_vision_supported("image/webp") is True

    def test_is_vision_supported_with_unsupported_image_types(self):
        """Test is_vision_supported returns False for unsupported image types."""
        service = ExtractionService()
        assert service.is_vision_supported("image/bmp") is False
        assert service.is_vision_supported("image/tiff") is False
        assert service.is_vision_supported("image/svg+xml") is False

    def test_is_vision_supported_with_non_image_types(self):
        """Test is_vision_supported returns False for non-image types."""
        service = ExtractionService()
        assert service.is_vision_supported("application/pdf") is False
        assert service.is_vision_supported("text/plain") is False


class TestImageExtractor:
    """Tests for the ImageExtractor class."""

    @pytest.mark.asyncio
    async def test_extract_returns_document(self):
        """Test extract returns an ExtractedDocument with description."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="A detailed image description")]

        with patch("app.services.file.extraction.image.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            extractor = ImageExtractor()
            result = await extractor.extract(
                image_content=b"fake image bytes",
                mime_type="image/png",
                file_name="test.png",
            )

        assert result.title == "test.png"
        assert len(result.blocks) == 1
        assert result.blocks[0].text == "A detailed image description"
        assert result.blocks[0].location == {"type": "image"}
        assert result.metadata["source_type"] == "image"
        assert result.metadata["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_extract_rejects_oversized_images(self):
        """Test extract raises ValueError for images > 10MB."""
        oversized_content = b"x" * (MAX_IMAGE_SIZE_BYTES + 1)

        extractor = ImageExtractor()
        with pytest.raises(ValueError) as exc_info:
            await extractor.extract(
                image_content=oversized_content,
                mime_type="image/png",
                file_name="large.png",
            )

        assert "exceeds size limit" in str(exc_info.value)
        assert "10MB" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_normalizes_jpg_mime_type(self):
        """Test extract normalizes image/jpg to image/jpeg."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]

        with patch("app.services.file.extraction.image.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            extractor = ImageExtractor()
            await extractor.extract(
                image_content=b"fake image bytes",
                mime_type="image/jpg",
                file_name="test.jpg",
            )

            # Check the API was called with normalized mime type
            call_args = mock_client.messages.create.call_args
            messages = call_args.kwargs["messages"]
            image_source = messages[0]["content"][0]["source"]
            assert image_source["media_type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_extract_uses_custom_model(self):
        """Test ImageExtractor uses custom model when provided."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]

        with patch("app.services.file.extraction.image.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            extractor = ImageExtractor(model="claude-custom-model")
            await extractor.extract(
                image_content=b"fake image bytes",
                mime_type="image/png",
                file_name="test.png",
            )

            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["model"] == "claude-custom-model"

    @pytest.mark.asyncio
    async def test_extract_uses_fast_model_by_default(self):
        """Test ImageExtractor uses claude_fast_model by default."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Description")]

        with patch("app.services.file.extraction.image.get_client") as mock_get_client, \
             patch("app.services.file.extraction.image.settings") as mock_settings:
            mock_settings.claude_fast_model = "claude-haiku-test"
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            extractor = ImageExtractor()
            await extractor.extract(
                image_content=b"fake image bytes",
                mime_type="image/png",
                file_name="test.png",
            )

            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["model"] == "claude-haiku-test"


class TestExtractionServiceExtractImage:
    """Tests for ExtractionService.extract_image method."""

    @pytest.mark.asyncio
    async def test_extract_image_delegates_to_extractor(self):
        """Test extract_image delegates to ImageExtractor."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Image description")]

        with patch("app.services.file.extraction.image.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExtractionService()
            result = await service.extract_image(
                image_content=b"fake image bytes",
                mime_type="image/png",
                file_name="test.png",
            )

        assert result.title == "test.png"
        assert len(result.blocks) == 1
        assert result.blocks[0].text == "Image description"


class TestMaxImageSizeConstant:
    """Tests for MAX_IMAGE_SIZE_BYTES constant."""

    def test_max_image_size_is_10mb(self):
        """Test MAX_IMAGE_SIZE_BYTES is exactly 10MB."""
        assert MAX_IMAGE_SIZE_BYTES == 10 * 1024 * 1024
