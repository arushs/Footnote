"""Data models for document extraction."""

from dataclasses import dataclass, field


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
