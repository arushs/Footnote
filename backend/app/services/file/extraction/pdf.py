"""PDF text extraction using Mistral OCR."""

import base64
import logging

from mistralai import Mistral

from app.config import settings
from app.services.file.extraction.models import ExtractedDocument, TextBlock

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDFs using Mistral OCR via SDK."""

    def __init__(self):
        self.api_key = settings.mistral_api_key

    async def extract(self, pdf_content: bytes) -> ExtractedDocument:
        """
        Extract text from PDF using Mistral's OCR capabilities.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            ExtractedDocument with title, blocks, and metadata
        """
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY is not configured")

        pdf_base64 = base64.standard_b64encode(pdf_content).decode("utf-8")

        try:
            result = await self._call_mistral_ocr(pdf_base64)
            return self._parse_ocr_result(result)
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return self._fallback_extraction(pdf_content)

    async def _call_mistral_ocr(self, pdf_base64: str) -> dict:
        """Call Mistral OCR API using the official SDK."""
        async with Mistral(api_key=self.api_key) as client:
            ocr_response = await client.ocr.process_async(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{pdf_base64}",
                },
                include_image_base64=False,
            )
            # Convert SDK response to dict format for compatibility
            return {"pages": [{"markdown": page.markdown} for page in ocr_response.pages]}

    def _parse_ocr_result(self, result: dict) -> ExtractedDocument:
        """Parse Mistral OCR response into structured document."""
        blocks: list[TextBlock] = []
        title = None

        pages = result.get("pages", [])
        for page_idx, page in enumerate(pages):
            page_num = page_idx + 1
            markdown_content = page.get("markdown", "")

            if not markdown_content:
                continue

            page_blocks = self._parse_markdown_blocks(markdown_content, page_num)
            blocks.extend(page_blocks)

            if title is None and page_blocks:
                first_text = page_blocks[0].text
                if len(first_text) < 200:
                    title = first_text

        return ExtractedDocument(
            title=title,
            blocks=blocks,
            metadata={
                "source_type": "pdf",
                "page_count": len(pages),
                "block_count": len(blocks),
            },
        )

    def _parse_markdown_blocks(self, markdown: str, page_num: int) -> list[TextBlock]:
        """Parse markdown content into text blocks."""
        blocks: list[TextBlock] = []
        current_heading = None

        lines = markdown.split("\n")
        current_block_lines: list[str] = []
        block_index = 0

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("#"):
                if current_block_lines:
                    text = "\n".join(current_block_lines).strip()
                    if text:
                        blocks.append(
                            TextBlock(
                                text=text,
                                location={
                                    "type": "pdf",
                                    "page": page_num,
                                    "block_index": block_index,
                                },
                                heading_context=current_heading,
                            )
                        )
                        block_index += 1
                    current_block_lines = []

                heading_level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped.lstrip("#").strip()
                current_heading = heading_text

                blocks.append(
                    TextBlock(
                        text=heading_text,
                        location={
                            "type": "pdf",
                            "page": page_num,
                            "block_index": block_index,
                            "element_type": "heading",
                            "heading_level": heading_level,
                        },
                        heading_context=heading_text,
                    )
                )
                block_index += 1

            elif stripped == "":
                if current_block_lines:
                    text = "\n".join(current_block_lines).strip()
                    if text:
                        blocks.append(
                            TextBlock(
                                text=text,
                                location={
                                    "type": "pdf",
                                    "page": page_num,
                                    "block_index": block_index,
                                },
                                heading_context=current_heading,
                            )
                        )
                        block_index += 1
                    current_block_lines = []
            else:
                current_block_lines.append(stripped)

        if current_block_lines:
            text = "\n".join(current_block_lines).strip()
            if text:
                blocks.append(
                    TextBlock(
                        text=text,
                        location={
                            "type": "pdf",
                            "page": page_num,
                            "block_index": block_index,
                        },
                        heading_context=current_heading,
                    )
                )

        return blocks

    def _fallback_extraction(self, pdf_content: bytes) -> ExtractedDocument:
        """Fallback extraction when Mistral OCR fails."""
        logger.warning("Using fallback PDF extraction (no text will be extracted)")
        return ExtractedDocument(
            title=None,
            blocks=[],
            metadata={
                "source_type": "pdf",
                "extraction_failed": True,
                "error": "OCR extraction failed, no fallback available",
            },
        )
