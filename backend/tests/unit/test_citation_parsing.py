"""Tests for citation parsing functionality."""

import pytest

from app.services.generation import parse_citations, ParsedSegment


class TestCitationParsing:
    """Citation parsing is critical for the UI - test thoroughly."""

    def test_single_citation(self):
        """Test parsing text with a single citation."""
        text = "The revenue was $4.2M [1]."
        result = parse_citations(text)
        assert result == [
            ParsedSegment(type="text", content="The revenue was $4.2M "),
            ParsedSegment(type="citation", content="1"),
            ParsedSegment(type="text", content="."),
        ]

    def test_adjacent_citations(self):
        """[1][2] should parse as two separate citations."""
        text = "Growth was strong [1][2]."
        result = parse_citations(text)
        assert result == [
            ParsedSegment(type="text", content="Growth was strong "),
            ParsedSegment(type="citation", content="1"),
            ParsedSegment(type="citation", content="2"),
            ParsedSegment(type="text", content="."),
        ]

    def test_multi_digit_citation(self):
        """Test that multi-digit citation numbers are parsed correctly."""
        text = "See source [12] for details."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 1
        assert citations[0].content == "12"

    def test_no_citations(self):
        """Text without citations should return a single text segment."""
        text = "This text has no citations."
        result = parse_citations(text)
        assert len(result) == 1
        assert result[0].type == "text"
        assert result[0].content == text

    def test_citation_at_start(self):
        """Citation at the start of text should parse correctly."""
        text = "[1] This is the first point."
        result = parse_citations(text)
        assert result[0].type == "citation"
        assert result[0].content == "1"

    def test_array_bracket_not_matched(self):
        """array[0] should NOT be parsed as citation."""
        text = "Access array[0] for the first element."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 0

    def test_citation_in_parentheses(self):
        """Citations within parentheses should parse correctly."""
        text = "The data (see [1]) confirms this."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 1
        assert citations[0].content == "1"

    def test_repeated_same_citation(self):
        """Same citation used multiple times should be parsed each time."""
        text = "Revenue [1] and profit [1] both increased."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 2
        assert all(c.content == "1" for c in citations)

    def test_empty_string(self):
        """Empty string should return empty list."""
        result = parse_citations("")
        assert result == []

    def test_multiple_different_citations(self):
        """Multiple different citations should all be parsed."""
        text = "Data [1] shows growth [2] in Q4 [3]."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 3
        assert citations[0].content == "1"
        assert citations[1].content == "2"
        assert citations[2].content == "3"

    def test_citation_at_end(self):
        """Citation at the end of text without trailing text."""
        text = "This is supported by the data [1]"
        result = parse_citations(text)
        assert result[-1].type == "citation"
        assert result[-1].content == "1"

    def test_only_citation(self):
        """Text that is just a citation."""
        text = "[5]"
        result = parse_citations(text)
        assert len(result) == 1
        assert result[0].type == "citation"
        assert result[0].content == "5"

    def test_three_digit_citation(self):
        """Three-digit citation numbers should work."""
        text = "Reference [123] contains details."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 1
        assert citations[0].content == "123"

    def test_newline_preserved(self):
        """Newlines in text should be preserved."""
        text = "Line one [1].\nLine two [2]."
        result = parse_citations(text)
        text_segments = [s.content for s in result if s.type == "text"]
        assert any("\n" in s for s in text_segments)

    def test_object_property_not_matched(self):
        """obj[key] style access should not be matched."""
        text = "Use config[0] to get the first value."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 0

    def test_function_call_not_matched(self):
        """function[index] style should not be matched."""
        text = "Call getItems[0] to retrieve data."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 0

    def test_space_before_bracket_is_citation(self):
        """Space before bracket should match as citation."""
        text = "Some text [7] here."
        result = parse_citations(text)
        citations = [s for s in result if s.type == "citation"]
        assert len(citations) == 1
        assert citations[0].content == "7"
