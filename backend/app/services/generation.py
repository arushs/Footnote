"""Generation service for answer processing and citation parsing."""

import re
from dataclasses import dataclass


@dataclass
class ParsedSegment:
    """A segment of parsed text - either plain text or a citation."""

    type: str  # "text" or "citation"
    content: str


def parse_citations(text: str) -> list[ParsedSegment]:
    """
    Parse text and extract citations in [N] format.

    Citations are identified as square brackets containing only digits,
    but we exclude array-style indexing (e.g., array[0]) where the
    bracket is preceded by a word character.

    Args:
        text: The text to parse for citations

    Returns:
        List of ParsedSegment objects with type "text" or "citation"
    """
    if not text:
        return []

    segments: list[ParsedSegment] = []

    # Pattern matches [N] where N is one or more digits,
    # but NOT when preceded by a word character (to exclude array[0])
    pattern = r"(?<!\w)\[(\d+)\]"

    last_end = 0
    for match in re.finditer(pattern, text):
        # Add any text before this citation
        if match.start() > last_end:
            text_before = text[last_end : match.start()]
            if text_before:
                segments.append(ParsedSegment(type="text", content=text_before))

        # Add the citation
        citation_num = match.group(1)
        segments.append(ParsedSegment(type="citation", content=citation_num))

        last_end = match.end()

    # Add any remaining text after the last citation
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining:
            segments.append(ParsedSegment(type="text", content=remaining))

    # If no citations were found, return the whole text as a single segment
    if not segments and text:
        segments.append(ParsedSegment(type="text", content=text))

    return segments


def extract_citation_numbers(text: str) -> set[int]:
    """
    Extract unique citation numbers from text.

    Args:
        text: The text containing citations

    Returns:
        Set of citation numbers found in the text
    """
    pattern = r"(?<!\w)\[(\d+)\]"
    matches = re.findall(pattern, text)
    return {int(m) for m in matches}
