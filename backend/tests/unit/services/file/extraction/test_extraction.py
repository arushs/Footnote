"""Tests for the extraction service."""

import pytest

from app.services.file.extraction import (
    ExtractedDocument,
    ExtractionService,
    GoogleDocsExtractor,
    PDFExtractor,
    TextBlock,
)


class TestGoogleDocsExtractor:
    """Tests for Google Docs HTML extraction."""

    def test_extract_simple_document(self):
        """Test extraction from a simple HTML document."""
        html = """
        <html>
            <head><title>Test Document</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>First paragraph of content.</p>
                <p>Second paragraph with more text.</p>
            </body>
        </html>
        """
        extractor = GoogleDocsExtractor()
        result = extractor.extract(html)

        assert result.title == "Test Document"
        assert len(result.blocks) == 3
        assert result.blocks[0].text == "Main Heading"
        assert result.blocks[0].location["element_type"] == "heading"
        assert result.blocks[1].text == "First paragraph of content."
        assert result.blocks[1].location["element_type"] == "paragraph"

    def test_extract_heading_hierarchy(self):
        """Test that heading context is properly tracked."""
        html = """
        <html>
            <body>
                <h1>Chapter 1</h1>
                <h2>Section 1.1</h2>
                <p>Content under section 1.1</p>
                <h2>Section 1.2</h2>
                <p>Content under section 1.2</p>
                <h1>Chapter 2</h1>
                <p>Content under chapter 2</p>
            </body>
        </html>
        """
        extractor = GoogleDocsExtractor()
        result = extractor.extract(html)

        paragraphs = [b for b in result.blocks if b.location.get("element_type") == "paragraph"]

        assert paragraphs[0].heading_context == "Chapter 1 > Section 1.1"
        assert paragraphs[1].heading_context == "Chapter 1 > Section 1.2"
        assert paragraphs[2].heading_context == "Chapter 2"

    def test_extract_lists(self):
        """Test extraction of list content."""
        html = """
        <html>
            <body>
                <h1>Shopping List</h1>
                <ul>
                    <li>Apples</li>
                    <li>Bananas</li>
                    <li>Oranges</li>
                </ul>
            </body>
        </html>
        """
        extractor = GoogleDocsExtractor()
        result = extractor.extract(html)

        list_block = next(b for b in result.blocks if b.location.get("element_type") == "list")
        assert "- Apples" in list_block.text
        assert "- Bananas" in list_block.text
        assert list_block.heading_context == "Shopping List"

    def test_extract_table(self):
        """Test extraction of table content."""
        html = """
        <html>
            <body>
                <h1>Data Table</h1>
                <table>
                    <tr><th>Name</th><th>Value</th></tr>
                    <tr><td>Alpha</td><td>100</td></tr>
                    <tr><td>Beta</td><td>200</td></tr>
                </table>
            </body>
        </html>
        """
        extractor = GoogleDocsExtractor()
        result = extractor.extract(html)

        table_block = next(b for b in result.blocks if b.location.get("element_type") == "table")
        assert "Name | Value" in table_block.text
        assert "Alpha | 100" in table_block.text

    def test_extract_empty_paragraphs_ignored(self):
        """Test that empty paragraphs are ignored."""
        html = """
        <html>
            <body>
                <p>Real content</p>
                <p>   </p>
                <p></p>
                <p>More content</p>
            </body>
        </html>
        """
        extractor = GoogleDocsExtractor()
        result = extractor.extract(html)

        assert len(result.blocks) == 2
        assert result.blocks[0].text == "Real content"
        assert result.blocks[1].text == "More content"

    def test_title_fallback_to_h1(self):
        """Test that title falls back to first h1 if no title tag."""
        html = """
        <html>
            <body>
                <h1>Document Title From H1</h1>
                <p>Some content.</p>
            </body>
        </html>
        """
        extractor = GoogleDocsExtractor()
        result = extractor.extract(html)

        assert result.title == "Document Title From H1"


class TestPDFExtractor:
    """Tests for PDF extraction logic."""

    def test_parse_markdown_blocks(self):
        """Test parsing of markdown content into blocks."""
        extractor = PDFExtractor()
        markdown = """# Main Title

This is the first paragraph of text.
It spans multiple lines.

## Section One

Content under section one.

Another paragraph here.

## Section Two

Final content block.
"""
        blocks = extractor._parse_markdown_blocks(markdown, page_num=1)

        assert len(blocks) >= 5
        assert blocks[0].text == "Main Title"
        assert blocks[0].location["element_type"] == "heading"
        assert blocks[0].location["page"] == 1

        paragraphs = [b for b in blocks if "element_type" not in b.location]
        assert any("first paragraph" in b.text for b in paragraphs)

    def test_parse_markdown_heading_context(self):
        """Test that heading context is tracked through markdown."""
        extractor = PDFExtractor()
        markdown = """# Chapter

## Section

Paragraph under section.
"""
        blocks = extractor._parse_markdown_blocks(markdown, page_num=1)

        paragraph = next(b for b in blocks if "element_type" not in b.location)
        assert paragraph.heading_context == "Section"

    def test_fallback_extraction(self):
        """Test fallback extraction when OCR fails."""
        extractor = PDFExtractor()
        result = extractor._fallback_extraction(b"dummy pdf content")

        assert result.title is None
        assert len(result.blocks) == 0
        assert result.metadata["extraction_failed"] is True


class TestExtractionService:
    """Tests for the unified extraction service."""

    def test_is_google_doc(self):
        """Test Google Doc mime type detection."""
        service = ExtractionService()
        assert service.is_google_doc("application/vnd.google-apps.document") is True
        assert service.is_google_doc("application/pdf") is False

    def test_is_pdf(self):
        """Test PDF mime type detection."""
        service = ExtractionService()
        assert service.is_pdf("application/pdf") is True
        assert service.is_pdf("application/vnd.google-apps.document") is False

    def test_is_supported(self):
        """Test supported mime type detection."""
        service = ExtractionService()
        assert service.is_supported("application/vnd.google-apps.document") is True
        assert service.is_supported("application/pdf") is True
        assert service.is_supported("image/png") is False
        assert service.is_supported("text/plain") is False

    @pytest.mark.asyncio
    async def test_extract_google_doc(self):
        """Test extraction via unified service."""
        service = ExtractionService()
        html = "<html><head><title>Test</title></head><body><p>Content</p></body></html>"

        result = await service.extract_google_doc(html)

        assert result.title == "Test"
        assert len(result.blocks) == 1
        assert result.blocks[0].text == "Content"


class TestTextBlock:
    """Tests for TextBlock dataclass."""

    def test_text_block_creation(self):
        """Test basic TextBlock creation."""
        block = TextBlock(
            text="Sample text",
            location={"type": "doc", "para_index": 0},
            heading_context="Introduction",
        )

        assert block.text == "Sample text"
        assert block.location["type"] == "doc"
        assert block.heading_context == "Introduction"

    def test_text_block_without_heading_context(self):
        """Test TextBlock without heading context."""
        block = TextBlock(text="Text", location={"type": "pdf", "page": 1})

        assert block.heading_context is None


class TestExtractedDocument:
    """Tests for ExtractedDocument dataclass."""

    def test_extracted_document_creation(self):
        """Test ExtractedDocument creation."""
        blocks = [
            TextBlock(text="Block 1", location={"type": "doc"}),
            TextBlock(text="Block 2", location={"type": "doc"}),
        ]
        doc = ExtractedDocument(
            title="My Document",
            blocks=blocks,
            metadata={"source_type": "google_doc"},
        )

        assert doc.title == "My Document"
        assert len(doc.blocks) == 2
        assert doc.metadata["source_type"] == "google_doc"

    def test_extracted_document_default_metadata(self):
        """Test ExtractedDocument with default metadata."""
        doc = ExtractedDocument(title=None, blocks=[])

        assert doc.metadata == {}
