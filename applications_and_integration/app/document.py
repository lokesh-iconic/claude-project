"""
app/document.py -- Document ingestion and section parsing.

Handles text file uploads, extracts content, and splits into named sections
for citation referencing. In production, this would integrate with a PDF
parser (e.g., PyMuPDF, pdfplumber) but for the assignment we work with
plain text files that simulate structured documents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DocumentSection:
    """A named section within a document."""
    name: str
    content: str
    start_char: int  # Character offset in the original document
    end_char: int


@dataclass
class ParsedDocument:
    """A parsed document with extracted sections."""
    filename: str
    raw_content: str
    sections: list[DocumentSection]
    uploaded_at: datetime = field(default_factory=datetime.now)

    @property
    def char_count(self) -> int:
        return len(self.raw_content)

    @property
    def section_count(self) -> int:
        return len(self.sections)

    def get_section_names(self) -> list[str]:
        """Return all section names for citation matching."""
        return [s.name for s in self.sections]

    def find_section(self, query: str) -> Optional[DocumentSection]:
        """Find a section by name (case-insensitive partial match)."""
        query_lower = query.lower()
        for section in self.sections:
            if query_lower in section.name.lower():
                return section
        return None


def parse_document(filename: str, content: str) -> ParsedDocument:
    """
    Parse a text document into sections.

    Section detection heuristics:
    1. Lines starting with "=== ... ===" (our sample document format)
    2. Lines starting with "Section N:" or "Article N:"
    3. Lines that are all-caps headers
    4. Numbered headers like "1.1 Title"

    If no sections are detected, the entire document is treated as one section.
    """
    sections: list[DocumentSection] = []
    lines = content.split("\n")

    # Regex patterns for section headers
    patterns = [
        re.compile(r"^===\s*(.+?)\s*===\s*$"),                  # === Section Name ===
        re.compile(r"^(Section\s+\d+[\.\d]*\s*:.*)$", re.I),    # Section N: Title
        re.compile(r"^(Article\s+\d+[\.\d]*\s*:.*)$", re.I),    # Article N: Title
        re.compile(r"^([A-Z][A-Z\s\-&]{10,})$"),                # ALL CAPS HEADER
    ]

    # Find all section boundaries
    boundaries: list[tuple[int, str, int]] = []  # (line_index, section_name, char_offset)
    char_offset = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        for pattern in patterns:
            match = pattern.match(stripped)
            if match:
                section_name = match.group(1).strip("= ").strip()
                boundaries.append((i, section_name, char_offset))
                break
        char_offset += len(line) + 1  # +1 for newline

    if not boundaries:
        # No sections found -- treat entire document as one section
        sections.append(DocumentSection(
            name="Full Document",
            content=content,
            start_char=0,
            end_char=len(content),
        ))
    else:
        # Build sections from boundaries
        for idx, (line_idx, name, start_char) in enumerate(boundaries):
            # Section content runs from this header to the next header (or end)
            if idx + 1 < len(boundaries):
                next_line_idx = boundaries[idx + 1][0]
                end_char = boundaries[idx + 1][2]
            else:
                next_line_idx = len(lines)
                end_char = len(content)

            section_lines = lines[line_idx:next_line_idx]
            section_content = "\n".join(section_lines).strip()

            if section_content:  # Skip empty sections
                sections.append(DocumentSection(
                    name=name,
                    content=section_content,
                    start_char=start_char,
                    end_char=end_char,
                ))

    return ParsedDocument(
        filename=filename,
        raw_content=content,
        sections=sections,
    )
