"""Text extraction service for Google Docs and PDFs."""

import base64
import logging
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag
from mistralai import Mistral

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """A structural unit of text from a document."""

    text: str
    location: dict
    heading_context: str | None = None


@dataclass
class ExtractedDocument:
    """Result of text extraction from a document."""

    title: str | None
    blocks: list[TextBlock]
    metadata: dict = field(default_factory=dict)


class GoogleDocsExtractor:
    """Extract structured text from Google Docs HTML export."""

    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def extract(self, html_content: str) -> ExtractedDocument:
        """
        Parse Google Docs HTML export and extract structured text blocks.

        Args:
            html_content: HTML string from Google Docs export

        Returns:
            ExtractedDocument with title, blocks, and metadata
        """
        soup = BeautifulSoup(html_content, "lxml")

        title = self._extract_title(soup)
        blocks = self._extract_blocks(soup)

        return ExtractedDocument(
            title=title,
            blocks=blocks,
            metadata={"source_type": "google_doc", "block_count": len(blocks)},
        )

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        """Extract document title from HTML."""
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return None

    def _extract_blocks(self, soup: BeautifulSoup) -> list[TextBlock]:
        """Extract text blocks with heading context."""
        blocks: list[TextBlock] = []
        heading_stack: list[tuple[int, str]] = []
        body = soup.find("body")

        if not body:
            return blocks

        para_index = 0

        for element in body.descendants:
            if not isinstance(element, Tag):
                continue

            tag_name = element.name.lower() if element.name else ""

            if tag_name in self.HEADING_TAGS:
                text = element.get_text(strip=True)
                if not text:
                    continue

                level = int(tag_name[1])
                heading_stack = [
                    (lvl, txt) for lvl, txt in heading_stack if lvl < level
                ]
                heading_stack.append((level, text))

                heading_path = self._build_heading_path(heading_stack)
                blocks.append(
                    TextBlock(
                        text=text,
                        location={
                            "type": "doc",
                            "heading_path": heading_path,
                            "element_type": "heading",
                            "heading_level": level,
                        },
                        heading_context=heading_path,
                    )
                )

            elif tag_name == "p":
                text = element.get_text(strip=True)
                if not text:
                    continue

                if element.find_parent(self.HEADING_TAGS):
                    continue

                heading_path = self._build_heading_path(heading_stack)
                blocks.append(
                    TextBlock(
                        text=text,
                        location={
                            "type": "doc",
                            "heading_path": heading_path,
                            "element_type": "paragraph",
                            "para_index": para_index,
                        },
                        heading_context=heading_path if heading_path else None,
                    )
                )
                para_index += 1

            elif tag_name in ("ul", "ol"):
                if element.find_parent(("ul", "ol")):
                    continue

                text = self._extract_list_text(element)
                if not text:
                    continue

                heading_path = self._build_heading_path(heading_stack)
                blocks.append(
                    TextBlock(
                        text=text,
                        location={
                            "type": "doc",
                            "heading_path": heading_path,
                            "element_type": "list",
                            "para_index": para_index,
                        },
                        heading_context=heading_path if heading_path else None,
                    )
                )
                para_index += 1

            elif tag_name == "table":
                text = self._extract_table_text(element)
                if not text:
                    continue

                heading_path = self._build_heading_path(heading_stack)
                blocks.append(
                    TextBlock(
                        text=text,
                        location={
                            "type": "doc",
                            "heading_path": heading_path,
                            "element_type": "table",
                            "para_index": para_index,
                        },
                        heading_context=heading_path if heading_path else None,
                    )
                )
                para_index += 1

        return blocks

    def _build_heading_path(self, heading_stack: list[tuple[int, str]]) -> str:
        """Build a heading path string from the stack."""
        if not heading_stack:
            return ""
        return " > ".join(text for _, text in heading_stack)

    def _extract_list_text(self, list_element: Tag) -> str:
        """Extract text from a list element, preserving structure."""
        items = []
        for li in list_element.find_all("li", recursive=False):
            text = li.get_text(strip=True)
            if text:
                items.append(f"- {text}")
        return "\n".join(items)

    def _extract_table_text(self, table_element: Tag) -> str:
        """Extract text from a table element."""
        rows = []
        for tr in table_element.find_all("tr"):
            cells = []
            for cell in tr.find_all(["td", "th"]):
                text = cell.get_text(strip=True)
                cells.append(text)
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)


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

    def _parse_markdown_blocks(
        self, markdown: str, page_num: int
    ) -> list[TextBlock]:
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


class ExtractionService:
    """Unified text extraction service for multiple document types."""

    GOOGLE_DOC_MIMETYPES = {
        "application/vnd.google-apps.document",
    }

    PDF_MIMETYPES = {
        "application/pdf",
    }

    # Image types that should be skipped (not supported for text extraction)
    IMAGE_MIMETYPES = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "image/svg+xml",
        "application/vnd.google-apps.photo",
    }

    def __init__(self):
        self.google_docs_extractor = GoogleDocsExtractor()
        self.pdf_extractor = PDFExtractor()

    async def extract_google_doc(self, html_content: str) -> ExtractedDocument:
        """Extract text from Google Docs HTML export."""
        return self.google_docs_extractor.extract(html_content)

    async def extract_pdf(self, pdf_content: bytes) -> ExtractedDocument:
        """Extract text from PDF using Mistral OCR."""
        return await self.pdf_extractor.extract(pdf_content)

    def is_google_doc(self, mime_type: str) -> bool:
        """Check if mime type is a Google Doc."""
        return mime_type in self.GOOGLE_DOC_MIMETYPES

    def is_pdf(self, mime_type: str) -> bool:
        """Check if mime type is a PDF."""
        return mime_type in self.PDF_MIMETYPES

    def is_image(self, mime_type: str) -> bool:
        """Check if mime type is an image (not supported for extraction)."""
        return mime_type in self.IMAGE_MIMETYPES or mime_type.startswith("image/")

    def is_supported(self, mime_type: str) -> bool:
        """Check if the mime type is supported for extraction."""
        return self.is_google_doc(mime_type) or self.is_pdf(mime_type)
