"""Image description extraction using Claude Vision."""

import base64
import logging
from typing import cast

from anthropic.types import ImageBlockParam, TextBlockParam
from anthropic.types import TextBlock as AnthropicTextBlock
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.services.anthropic import get_client
from app.services.file.extraction.models import ExtractedDocument, TextBlock

logger = logging.getLogger(__name__)

# Max image size for processing (10MB)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024


class ImageExtractor:
    """Extract searchable text descriptions from images using Claude Vision."""

    VISION_PROMPT = (
        "This image is named '{file_name}'. Please describe this image in detail, including:\n"
        "1. What the image shows (objects, people, scenes, diagrams, charts, etc.)\n"
        "2. Any text visible in the image (transcribe it)\n"
        "3. Key visual details that might be relevant for search and retrieval\n"
        "4. The overall context or purpose of the image if apparent"
    )

    def __init__(self, model: str | None = None):
        """
        Initialize the image extractor.

        Args:
            model: Claude model to use (defaults to claude_fast_model for cost efficiency)
        """
        self.model = model or settings.claude_fast_model

    async def extract(
        self,
        image_content: bytes,
        mime_type: str,
        file_name: str,
    ) -> ExtractedDocument:
        """
        Extract a text description from an image using Claude Vision.

        Args:
            image_content: Raw image bytes
            mime_type: Image MIME type (e.g., 'image/png')
            file_name: Name of the image file for context

        Returns:
            ExtractedDocument with the image description as a single block

        Raises:
            ValueError: If image exceeds size limit
        """
        if len(image_content) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Image {file_name} exceeds size limit: "
                f"{len(image_content) / 1024 / 1024:.1f}MB > 10MB"
            )

        description = await self._describe_image(image_content, mime_type, file_name)

        return ExtractedDocument(
            title=file_name,
            blocks=[
                TextBlock(
                    text=description,
                    location={"type": "image"},
                    heading_context=None,
                )
            ],
            metadata={"source_type": "image", "mime_type": mime_type},
        )

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _describe_image(
        self,
        image_content: bytes,
        mime_type: str,
        file_name: str,
    ) -> str:
        """Call Claude Vision API to describe the image."""
        client = get_client()

        # Normalize mime type for Claude API
        media_type = mime_type
        if media_type == "image/jpg":
            media_type = "image/jpeg"

        logger.info(f"Analyzing image {file_name} with {self.model}")

        image_block: ImageBlockParam = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,  # type: ignore[typeddict-item]
                "data": base64.b64encode(image_content).decode("utf-8"),
            },
        }
        text_block: TextBlockParam = {
            "type": "text",
            "text": self.VISION_PROMPT.format(file_name=file_name),
        }

        response = await client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [image_block, text_block],
                }
            ],
        )

        response_block = cast(AnthropicTextBlock, response.content[0])
        description = response_block.text
        logger.info(f"Generated {len(description)} char description for {file_name}")
        return description
