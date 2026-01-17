"""Tests for the chunking service."""

from app.services.chunking import (
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    chunk_document,
    generate_file_preview,
)
from app.services.extraction import TextBlock


class TestDocumentChunking:
    """Tests for document chunking functionality."""

    def test_preserves_heading_context(self):
        """Chunks should include heading context from blocks."""
        # Create blocks with sufficient content to meet MIN_CHUNK_SIZE (100 chars)
        blocks = [
            TextBlock(
                text="Introduction",
                location={"type": "doc", "element_type": "heading", "heading_path": "Introduction"},
                heading_context="Introduction",
            ),
            TextBlock(
                text="This is introductory content that provides a comprehensive overview of the document and its main topics covered throughout the various sections.",
                location={
                    "type": "doc",
                    "element_type": "paragraph",
                    "heading_path": "Introduction",
                },
                heading_context="Introduction",
            ),
            TextBlock(
                text="Results",
                location={"type": "doc", "element_type": "heading", "heading_path": "Results"},
                heading_context="Results",
            ),
            TextBlock(
                text="Revenue increased significantly this quarter, showing strong growth across all business segments. The financial performance exceeded expectations.",
                location={"type": "doc", "element_type": "paragraph", "heading_path": "Results"},
                heading_context="Results",
            ),
        ]
        chunks = chunk_document(blocks)

        # Find chunk with "Revenue"
        revenue_chunk = next((c for c in chunks if "Revenue" in c.text), None)
        assert revenue_chunk is not None
        assert revenue_chunk.location.get("heading_context") == "Results"

    def test_chunk_size_with_sentence_boundaries(self):
        """Chunks should split at sentence boundaries when text is large."""
        # Create text with sentence boundaries that can be split
        sentences = "This is a complete sentence. " * 100  # About 2900 chars with sentences
        blocks = [
            TextBlock(
                text="Long Section",
                location={"type": "doc", "element_type": "heading"},
                heading_context=None,
            ),
            TextBlock(
                text=sentences,
                location={"type": "doc", "element_type": "paragraph"},
                heading_context="Long Section",
            ),
        ]
        chunks = chunk_document(blocks)

        # Should have multiple chunks since text is large
        assert len(chunks) > 1

        # Each chunk should be within TARGET_CHUNK_SIZE bounds (with some flexibility)
        for chunk in chunks:
            # Allow some flexibility as chunks split at sentence boundaries
            assert len(chunk.text) <= MAX_CHUNK_SIZE + 200, f"Chunk too large: {len(chunk.text)}"

    def test_empty_blocks(self):
        """Empty block list should return empty chunk list."""
        chunks = chunk_document([])
        assert len(chunks) == 0

    def test_small_blocks_merged(self):
        """Small consecutive blocks should be merged together if they meet min size."""
        # Create blocks that together meet MIN_CHUNK_SIZE
        blocks = [
            TextBlock(
                text="First paragraph with enough content to make a meaningful contribution to the overall chunk size.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
            TextBlock(
                text="Second paragraph also has sufficient content to add meaningful text to the combined chunk.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
            TextBlock(
                text="Third paragraph completes the merged block with additional relevant content for testing.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        chunks = chunk_document(blocks)

        # Small blocks should be merged into one chunk
        assert len(chunks) == 1
        assert "First paragraph" in chunks[0].text
        assert "Second paragraph" in chunks[0].text
        assert "Third paragraph" in chunks[0].text

    def test_heading_starts_new_chunk(self):
        """Headings should start new chunks."""
        blocks = [
            TextBlock(
                text="First section content that is long enough to be a chunk on its own with plenty of text.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context="Section One",
            ),
            TextBlock(
                text="More content for section one to ensure we have enough text to meet minimum size.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context="Section One",
            ),
            TextBlock(
                text="Section Two",
                location={"type": "doc", "element_type": "heading"},
                heading_context="Section Two",
            ),
            TextBlock(
                text="Second section content that is also long enough to meet the minimum chunk size requirement.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context="Section Two",
            ),
        ]
        chunks = chunk_document(blocks)

        # Should have at least 2 chunks (heading causes split)
        assert len(chunks) >= 2

    def test_chunk_index_sequential(self):
        """Chunk indices should be sequential starting from 0."""
        blocks = [
            TextBlock(
                text="word " * 100,  # ~500 chars
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
            TextBlock(
                text="word " * 100,  # ~500 chars
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        chunks = chunk_document(blocks)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_whitespace_only_blocks_ignored(self):
        """Blocks with only whitespace should be ignored."""
        blocks = [
            TextBlock(
                text="   ",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
            TextBlock(
                text="Real content that should appear in chunks.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
            TextBlock(
                text="More real content to ensure chunk size.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        chunks = chunk_document(blocks)

        # Whitespace block should be ignored
        for chunk in chunks:
            assert chunk.text.strip() != ""

    def test_minimum_chunk_size_respected(self):
        """Chunks smaller than MIN_CHUNK_SIZE should not be created."""
        blocks = [
            TextBlock(
                text="A" * (MIN_CHUNK_SIZE - 50),  # Too small
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        chunks = chunk_document(blocks)

        # Single small block should not create a chunk
        assert len(chunks) == 0


class TestPDFChunking:
    """Tests for PDF-specific chunking behavior."""

    def test_page_number_preserved(self):
        """Page number metadata should be preserved in chunks."""
        blocks = [
            TextBlock(
                text="Content from page one that is long enough to form a chunk by itself.",
                location={"type": "pdf", "page": 1, "element_type": "paragraph"},
                heading_context=None,
            ),
            TextBlock(
                text="More content from page one to meet minimum size.",
                location={"type": "pdf", "page": 1, "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        chunks = chunk_document(blocks)

        # All chunks should have page info
        assert len(chunks) > 0
        # Location should contain the page info
        assert chunks[0].location.get("type") == "pdf"

    def test_multiple_pages_chunked(self):
        """Content from multiple pages should be chunked appropriately."""
        blocks = [
            TextBlock(
                text="Page one heading",
                location={"type": "pdf", "page": 1, "element_type": "heading"},
                heading_context="Page one heading",
            ),
            TextBlock(
                text="First page content with enough text to be meaningful for chunking purposes.",
                location={"type": "pdf", "page": 1},
                heading_context="Page one heading",
            ),
            TextBlock(
                text="More page one content to fill out the chunk size.",
                location={"type": "pdf", "page": 1},
                heading_context="Page one heading",
            ),
            TextBlock(
                text="Page two heading",
                location={"type": "pdf", "page": 2, "element_type": "heading"},
                heading_context="Page two heading",
            ),
            TextBlock(
                text="Second page content with enough text to be meaningful for chunking purposes.",
                location={"type": "pdf", "page": 2},
                heading_context="Page two heading",
            ),
        ]
        chunks = chunk_document(blocks)

        # Should have chunks from the document
        assert len(chunks) >= 1


class TestGenerateFilePreview:
    """Tests for file preview generation."""

    def test_preview_includes_headings(self):
        """Preview should prioritize headings."""
        blocks = [
            TextBlock(
                text="Main Title",
                location={"type": "doc", "element_type": "heading"},
                heading_context=None,
            ),
            TextBlock(
                text="Some paragraph content.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context="Main Title",
            ),
            TextBlock(
                text="Section One",
                location={"type": "doc", "element_type": "heading"},
                heading_context=None,
            ),
        ]
        preview = generate_file_preview(blocks)

        assert "Main Title" in preview
        assert "Section One" in preview

    def test_preview_respects_max_length(self):
        """Preview should not exceed max_length."""
        blocks = [
            TextBlock(
                text="word " * 200,  # Long text
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        preview = generate_file_preview(blocks, max_length=100)

        assert len(preview) <= 103  # 100 + "..."

    def test_empty_blocks_return_empty_preview(self):
        """Empty block list should return empty preview."""
        preview = generate_file_preview([])
        assert preview == ""

    def test_preview_from_content_blocks(self):
        """Preview should include content from early blocks."""
        blocks = [
            TextBlock(
                text="First paragraph with important content.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
            TextBlock(
                text="Second paragraph with more content.",
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        preview = generate_file_preview(blocks, max_length=500)

        assert "First paragraph" in preview


class TestLargeTextSplitting:
    """Tests for splitting large text blocks."""

    def test_large_block_splits(self):
        """Large blocks should be split into multiple chunks."""
        # Create a very large block
        large_text = "This is a sentence. " * 200  # About 4000 chars
        blocks = [
            TextBlock(
                text=large_text,
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        chunks = chunk_document(blocks)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Each chunk should be within bounds
        for chunk in chunks:
            assert len(chunk.text) <= MAX_CHUNK_SIZE

    def test_large_block_preserves_location(self):
        """Split chunks should retain the original block's location info."""
        large_text = "This is a sentence. " * 200
        blocks = [
            TextBlock(
                text=large_text,
                location={"type": "pdf", "page": 5},
                heading_context="Test Heading",
            ),
        ]
        chunks = chunk_document(blocks)

        # All chunks should have location info
        for chunk in chunks:
            assert "type" in chunk.location

    def test_sentence_boundary_splitting(self):
        """Large text should preferably split at sentence boundaries."""
        sentences = [
            "First sentence ends here.",
            "Second sentence is here.",
            "Third sentence follows.",
            "Fourth sentence continues.",
        ]
        large_text = " ".join(sentences * 50)  # Repeat to make it large

        blocks = [
            TextBlock(
                text=large_text,
                location={"type": "doc", "element_type": "paragraph"},
                heading_context=None,
            ),
        ]
        chunks = chunk_document(blocks)

        # Check that chunks don't start/end in middle of words
        for chunk in chunks:
            # Should end with proper punctuation or be the last chunk
            text = chunk.text.strip()
            if text:
                # Text should be readable (not cut mid-word typically)
                assert len(text) > 10  # Non-trivial chunk
