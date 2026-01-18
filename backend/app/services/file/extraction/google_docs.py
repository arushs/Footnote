"""Google Docs HTML extraction."""

from bs4 import BeautifulSoup, Tag

from app.services.file.extraction.models import ExtractedDocument, TextBlock


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
                heading_stack = [(lvl, txt) for lvl, txt in heading_stack if lvl < level]
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
