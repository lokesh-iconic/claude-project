"""
tests/test_models.py -- Schema validation tests.

Validates that all Pydantic models enforce their constraints correctly
and that JSON schema export works as expected.
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime

import pytest

# Add parent dirs to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import (
    Citation, ConfidenceLevel, StructuredAnswer,
    QuestionRequest, QuestionResponse, DocumentUploadResponse,
    SessionInfo, export_schemas,
)
from app.document import parse_document


# ---------------------------------------------------------------------------
# Citation Schema Tests
# ---------------------------------------------------------------------------

class TestCitation:
    def test_valid_citation(self):
        c = Citation(section="Section 2.3", quote="Employees receive 10 days", relevance=0.85)
        assert c.section == "Section 2.3"
        assert c.relevance == 0.85

    def test_relevance_bounds(self):
        """Relevance must be 0.0 to 1.0."""
        with pytest.raises(Exception):
            Citation(section="S1", quote="test", relevance=1.5)
        with pytest.raises(Exception):
            Citation(section="S1", quote="test", relevance=-0.1)

    def test_edge_relevance_values(self):
        c_zero = Citation(section="S1", quote="test", relevance=0.0)
        c_one = Citation(section="S1", quote="test", relevance=1.0)
        assert c_zero.relevance == 0.0
        assert c_one.relevance == 1.0


# ---------------------------------------------------------------------------
# StructuredAnswer Schema Tests
# ---------------------------------------------------------------------------

class TestStructuredAnswer:
    def test_valid_answer(self):
        answer = StructuredAnswer(
            answer="The PTO policy allows 15 days per year.",
            citations=[
                Citation(section="Section 3.1", quote="PTO accrues...", relevance=0.9),
            ],
            confidence=ConfidenceLevel.HIGH,
            follow_up_suggestions=["What about sick leave?"],
        )
        assert answer.confidence == ConfidenceLevel.HIGH
        assert len(answer.citations) == 1

    def test_empty_citations(self):
        """Answer with no citations should still be valid."""
        answer = StructuredAnswer(
            answer="Not found in the document.",
            confidence=ConfidenceLevel.NOT_FOUND,
        )
        assert answer.citations == []
        assert answer.follow_up_suggestions == []

    def test_confidence_enum_values(self):
        for level in ConfidenceLevel:
            answer = StructuredAnswer(
                answer="test", confidence=level,
            )
            assert answer.confidence == level


# ---------------------------------------------------------------------------
# QuestionRequest Tests
# ---------------------------------------------------------------------------

class TestQuestionRequest:
    def test_valid_question(self):
        q = QuestionRequest(question="What is the PTO policy?")
        assert q.question == "What is the PTO policy?"

    def test_empty_question_rejected(self):
        with pytest.raises(Exception):
            QuestionRequest(question="")

    def test_long_question_rejected(self):
        with pytest.raises(Exception):
            QuestionRequest(question="x" * 2001)


# ---------------------------------------------------------------------------
# DocumentUploadResponse Tests
# ---------------------------------------------------------------------------

class TestDocumentUploadResponse:
    def test_valid_response(self):
        r = DocumentUploadResponse(
            session_id="abc-123",
            document_name="test.txt",
            document_sections=5,
            document_chars=1000,
        )
        assert r.session_id == "abc-123"
        assert r.message == "Document uploaded successfully"


# ---------------------------------------------------------------------------
# Document Parsing Tests
# ---------------------------------------------------------------------------

class TestDocumentParsing:
    def test_parse_sections(self):
        content = (
            "=== Section 1: Introduction ===\n"
            "This is the intro.\n\n"
            "=== Section 2: Details ===\n"
            "Here are the details.\n"
        )
        doc = parse_document("test.txt", content)
        assert doc.section_count == 2
        assert doc.sections[0].name == "Section 1: Introduction"

    def test_no_sections(self):
        doc = parse_document("plain.txt", "Just plain text with no headers.")
        assert doc.section_count == 1
        assert doc.sections[0].name == "Full Document"

    def test_find_section(self):
        content = "=== Revenue ===\nRevenue is $50M\n=== Costs ===\nCosts are $30M\n"
        doc = parse_document("report.txt", content)
        found = doc.find_section("revenue")
        assert found is not None
        assert "Revenue" in found.name


# ---------------------------------------------------------------------------
# JSON Schema Export Tests
# ---------------------------------------------------------------------------

class TestSchemaExport:
    def test_export_produces_valid_json(self):
        schemas = export_schemas()
        json_str = json.dumps(schemas)
        assert len(json_str) > 100

    def test_export_contains_all_schemas(self):
        schemas = export_schemas()
        expected_keys = {"StructuredAnswer", "Citation", "QuestionResponse",
                         "DocumentUploadResponse", "SessionInfo"}
        assert expected_keys == set(schemas.keys())

    def test_citation_schema_has_required_fields(self):
        schema = Citation.model_json_schema()
        props = schema.get("properties", {})
        assert "section" in props
        assert "quote" in props
        assert "relevance" in props


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
