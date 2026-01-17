"""Unified extraction service for multiple document types."""

from app.services.extraction.google_docs import GoogleDocsExtractor
from app.services.extraction.models import ExtractedDocument
from app.services.extraction.pdf import PDFExtractor


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
