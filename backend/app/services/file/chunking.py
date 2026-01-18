"""Chunking service for splitting documents into embeddable chunks."""

from dataclasses import dataclass

from app.services.file.extraction import TextBlock


@dataclass
class DocumentChunk:
    """A chunk of text ready for embedding."""

    text: str
    location: dict
    chunk_index: int


# Target chunk size in characters (roughly 300-500 tokens)
TARGET_CHUNK_SIZE = 1500
# Maximum chunk size (hard limit)
MAX_CHUNK_SIZE = 2000
# Minimum chunk size (avoid tiny chunks)
MIN_CHUNK_SIZE = 100
# Overlap between chunks
OVERLAP_SIZE = 150


def chunk_document(blocks: list[TextBlock]) -> list[DocumentChunk]:
    """
    Convert text blocks into chunks suitable for embedding.

    This uses a semantic-aware chunking strategy:
    1. Respect document structure (headings, paragraphs)
    2. Merge small blocks together
    3. Split large blocks with overlap

    Args:
        blocks: List of text blocks from extraction

    Returns:
        List of document chunks with location metadata
    """
    if not blocks:
        return []

    chunks: list[DocumentChunk] = []
    current_text = ""
    current_location: dict | None = None
    chunk_index = 0

    for block in blocks:
        block_text = block.text.strip()
        if not block_text:
            continue

        # If this is a heading, it starts a new logical section
        is_heading = block.location.get("element_type") == "heading"

        # Decide whether to merge or start new chunk
        if current_text:
            combined_length = len(current_text) + len(block_text) + 2  # +2 for \n\n

            if is_heading or combined_length > TARGET_CHUNK_SIZE:
                # Flush current chunk
                if len(current_text) >= MIN_CHUNK_SIZE:
                    chunks.append(
                        DocumentChunk(
                            text=current_text,
                            location=current_location or {},
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1

                current_text = ""
                current_location = None

        # Handle the current block
        if len(block_text) > MAX_CHUNK_SIZE:
            # Split large blocks
            sub_chunks = _split_large_text(block_text, block.location, chunk_index)
            for sub_chunk in sub_chunks:
                chunks.append(sub_chunk)
                chunk_index += 1
        else:
            # Merge or start accumulating
            if current_text:
                current_text += "\n\n" + block_text
            else:
                current_text = block_text
                current_location = _merge_location(current_location, block.location)

            # Update location with heading context if available
            if block.heading_context and current_location:
                current_location["heading_context"] = block.heading_context

    # Flush remaining content
    if current_text and len(current_text) >= MIN_CHUNK_SIZE:
        chunks.append(
            DocumentChunk(
                text=current_text,
                location=current_location or {},
                chunk_index=chunk_index,
            )
        )

    return chunks


def _split_large_text(text: str, base_location: dict, start_index: int) -> list[DocumentChunk]:
    """Split a large text block into smaller chunks with overlap."""
    chunks = []

    # Split on sentence boundaries when possible
    sentences = _split_sentences(text)
    current_chunk = ""
    chunk_idx = start_index

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > TARGET_CHUNK_SIZE:
            if current_chunk:
                location = dict(base_location)
                location["sub_chunk"] = chunk_idx - start_index
                chunks.append(
                    DocumentChunk(
                        text=current_chunk.strip(),
                        location=location,
                        chunk_index=chunk_idx,
                    )
                )
                chunk_idx += 1

                # Start new chunk with overlap
                overlap_text = _get_overlap_text(current_chunk)
                current_chunk = overlap_text + " " + sentence if overlap_text else sentence
            else:
                current_chunk = sentence
        else:
            current_chunk = current_chunk + " " + sentence if current_chunk else sentence

    # Final chunk
    if current_chunk.strip():
        location = dict(base_location)
        location["sub_chunk"] = chunk_idx - start_index
        chunks.append(
            DocumentChunk(
                text=current_chunk.strip(),
                location=location,
                chunk_index=chunk_idx,
            )
        )

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences (simple heuristic)."""
    import re

    # Split on sentence-ending punctuation followed by space
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _get_overlap_text(text: str) -> str:
    """Get the last portion of text for overlap."""
    if len(text) <= OVERLAP_SIZE:
        return text

    # Try to break at a sentence boundary
    overlap_region = text[-OVERLAP_SIZE * 2 :]
    sentences = _split_sentences(overlap_region)
    if len(sentences) >= 2:
        return sentences[-1]

    # Fall back to character-based split
    return text[-OVERLAP_SIZE:]


def _merge_location(current: dict | None, new: dict) -> dict:
    """Merge location information from multiple blocks."""
    if current is None:
        return dict(new)

    merged = dict(current)

    # Keep the first location's base info (page, type)
    # Update heading context if new one is more specific
    if new.get("heading_path") and not merged.get("heading_path"):
        merged["heading_path"] = new["heading_path"]

    return merged


def generate_file_preview(blocks: list[TextBlock], max_length: int = 500) -> str:
    """
    Generate a preview/summary of the document for file-level embedding.

    Args:
        blocks: List of text blocks from extraction
        max_length: Maximum preview length

    Returns:
        Preview text string
    """
    if not blocks:
        return ""

    preview_parts = []
    current_length = 0

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        # Prioritize headings
        is_heading = block.location.get("element_type") == "heading"
        if is_heading:
            preview_parts.append(text)
            current_length += len(text)
        elif current_length < max_length:
            # Add first few content blocks
            remaining = max_length - current_length
            if len(text) > remaining:
                text = text[:remaining] + "..."
            preview_parts.append(text)
            current_length += len(text)

        if current_length >= max_length:
            break

    return "\n".join(preview_parts)
