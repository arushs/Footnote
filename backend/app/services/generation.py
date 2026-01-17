"""Generation service for citation extraction."""

import re


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
