"""
app/claude_client.py -- Claude API integration with streaming and prompt caching.

This module demonstrates the core Claude API mechanics required by the assignment:
  1. STREAMING: Uses client.messages.stream() for real-time token delivery
  2. PROMPT CACHING: Document content in system prompt with cache_control
  3. MESSAGES API: Proper multi-turn conversation with role alternation
  4. MOCK MODE: Deterministic responses when no API key is available

PROMPT CACHING ARCHITECTURE
=============================
The document content is placed in the system prompt (not user messages) with
cache_control: {"type": "ephemeral"}. This means:
  - First question against a document: full input token cost + cache write cost
  - Subsequent questions (within 5-min TTL): cache read cost only (~10% of full)
  - Different questions against the SAME document: all cache hits
  - Different documents: cache miss (new content, new cache entry)

This is optimal for the Q&A use case because:
  - The document is the STABLE prefix (doesn't change between questions)
  - The conversation history is the VARIABLE suffix (changes every turn)
  - Prompt caching is prefix-based, so stable-first ordering is required
"""

from __future__ import annotations

import json
import re
from typing import Generator, Optional

from app.config import (
    get_model_name, get_max_tokens, get_temperature,
    get_system_prompt, get_cache_config, get_api_key,
)
from app.document import ParsedDocument
from app.models import Citation, ConfidenceLevel, StructuredAnswer
from app.session import Session


_client_instance = None
_client_checked = False


def _get_client():
    """Get the Anthropic client, or None for mock mode or invalid key."""
    global _client_instance, _client_checked
    if _client_checked:
        return _client_instance

    api_key = get_api_key()
    if api_key is None:
        _client_checked = True
        _client_instance = None
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            client.models.list(limit=1)
            _client_instance = client
        except anthropic.AuthenticationError as auth_err:
            print(f"\n  [WARNING] ANTHROPIC_API_KEY from .env is invalid ({auth_err.message}).")
            print("  [WARNING] Running DocuQuery in MOCK mode. Update ANTHROPIC_API_KEY in .env for live mode.\n")
            _client_instance = None
        except Exception:
            _client_instance = client
    except Exception:
        _client_instance = None

    _client_checked = True
    return _client_instance


def _build_system_prompt(document: ParsedDocument) -> list[dict] | str:
    """
    Build the system prompt with document content and cache control.

    Structure (for caching):
      Block 1: System instruction (short, stable)
      Block 2: Document content (long, stable, CACHED)

    The cache_control marker goes on the LAST stable block, which is the
    document. Everything before it (the system instruction) is included
    in the cached prefix automatically.
    """
    cache_config = get_cache_config()
    system_text = get_system_prompt()

    # Format document with section markers for citation
    doc_sections = []
    for section in document.sections:
        doc_sections.append(f"[{section.name}]\n{section.content}")
    document_text = "\n\n---\n\n".join(doc_sections)

    use_caching = (
        cache_config.get("enabled", True)
        and len(document.raw_content) >= cache_config.get("min_document_length", 500)
    )

    if use_caching:
        # Return structured blocks with cache_control on the document block
        return [
            {
                "type": "text",
                "text": system_text.strip(),
            },
            {
                "type": "text",
                "text": (
                    f"Here is the document the user uploaded "
                    f"({document.filename}):\n\n{document_text}"
                ),
                "cache_control": {"type": cache_config.get("type", "ephemeral")},
            },
        ]
    else:
        # No caching -- simple string system prompt
        return f"{system_text}\n\nDocument ({document.filename}):\n\n{document_text}"


def _build_messages(session: Session, question: str) -> list[dict]:
    """
    Build the messages array for the API call.

    Conversation history comes from the session, plus the new question.
    The document is NOT in messages -- it's in the system prompt (for caching).
    """
    messages = session.get_messages_for_api()
    messages.append({"role": "user", "content": question})
    return messages


# ---------------------------------------------------------------------------
# Live API: Streaming
# ---------------------------------------------------------------------------

def ask_question_stream(
    session: Session,
    question: str,
) -> Generator[str, None, dict]:
    """
    Ask a question with streaming response.

    Yields text chunks as they arrive. Returns usage stats at the end.

    Usage:
        gen = ask_question_stream(session, "What is the PTO policy?")
        for chunk in gen:
            print(chunk, end="")
        # After generator exhausts, usage stats are available

    In live mode: uses client.messages.stream() with text_stream
    In mock mode: yields mock text in chunks
    """
    client = _get_client()

    if client is not None:
        try:
            yield from _stream_live(client, session, question)
        except Exception as e:
            print(f"  [Notice: Live streaming failed ({e}) — falling back to mock response]")
            yield from _stream_mock(session, question)
    else:
        yield from _stream_mock(session, question)


def _stream_live(
    client, session: Session, question: str
) -> Generator[str, None, dict]:
    """Stream response from Claude API."""
    system = _build_system_prompt(session.document)
    messages = _build_messages(session, question)

    with client.messages.stream(
        model=get_model_name(),
        max_tokens=get_max_tokens(),
        temperature=get_temperature(),
        system=system,
        messages=messages,
    ) as stream:
        full_text = ""
        for text in stream.text_stream:
            full_text += text
            yield text

        # Get final message for usage stats
        final = stream.get_final_message()
        usage = {
            "input_tokens": final.usage.input_tokens,
            "output_tokens": final.usage.output_tokens,
            "cache_creation_input_tokens": getattr(
                final.usage, "cache_creation_input_tokens", 0
            ),
            "cache_read_input_tokens": getattr(
                final.usage, "cache_read_input_tokens", 0
            ),
        }

        # Record the turn in session
        session.add_turn(question, full_text)

        # Check if summarization is needed
        if session.needs_summarization():
            session.summarize_history()

    return usage


def _stream_mock(
    session: Session, question: str
) -> Generator[str, None, dict]:
    """Mock streaming response for development without API key."""
    document = session.document
    question_lower = question.lower()

    # Find relevant sections by keyword matching
    relevant_sections = []
    for section in document.sections:
        section_lower = section.content.lower()
        # Check if any word from the question appears in the section
        question_words = set(re.findall(r"\w{4,}", question_lower))
        section_words = set(re.findall(r"\w{4,}", section_lower))
        overlap = question_words & section_words
        if overlap:
            relevant_sections.append((section, len(overlap)))

    # Sort by relevance (most keyword matches first)
    relevant_sections.sort(key=lambda x: x[1], reverse=True)

    if relevant_sections:
        top_section = relevant_sections[0][0]
        # Extract a relevant snippet (first 200 chars of matching section)
        snippet = top_section.content[:300].strip()
        answer = (
            f"Based on {top_section.name} of the document, "
            f"here is what I found:\n\n"
            f'"{snippet}..."\n\n'
            f"This section addresses your question about "
            f'"{question[:50]}". '
        )
        if len(relevant_sections) > 1:
            other_names = [s[0].name for s in relevant_sections[1:3]]
            answer += (
                f"Related information may also be found in: "
                f"{', '.join(other_names)}."
            )
    else:
        answer = (
            "This information is not covered in the uploaded document. "
            "The document contains the following sections: "
            f"{', '.join(document.get_section_names())}. "
            "Please try rephrasing your question or ask about a topic "
            "covered in these sections."
        )

    # Simulate streaming by yielding chunks
    words = answer.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield chunk

    # Record in session
    session.add_turn(question, answer)

    # Check if summarization is needed
    if session.needs_summarization():
        session.summarize_history()

    # Return mock usage stats
    is_first_question = len(session.history) == 1
    return {
        "input_tokens": len(document.raw_content) // 4 + len(question) // 4,
        "output_tokens": len(answer) // 4,
        "cache_creation_input_tokens": len(document.raw_content) // 4 if is_first_question else 0,
        "cache_read_input_tokens": 0 if is_first_question else len(document.raw_content) // 4,
    }


# ---------------------------------------------------------------------------
# Non-streaming variant (for structured responses)
# ---------------------------------------------------------------------------

def ask_question(session: Session, question: str) -> tuple[StructuredAnswer, dict]:
    """
    Ask a question and get a structured answer (non-streaming).

    Returns (StructuredAnswer, usage_dict).
    """
    # Collect streamed response
    full_text = ""
    usage = {}
    gen = ask_question_stream(session, question)

    try:
        while True:
            chunk = next(gen)
            full_text += chunk
    except StopIteration as e:
        usage = e.value or {}

    # Parse into structured answer
    structured = _parse_to_structured(full_text, session.document, question)

    return structured, usage


def _parse_to_structured(
    raw_text: str,
    document: ParsedDocument,
    question: str,
) -> StructuredAnswer:
    """
    Parse raw model output into a validated StructuredAnswer.

    Extracts citations by matching section references in the text,
    and determines confidence based on whether sections were found.
    """
    citations = []

    # Find cited sections
    for section in document.sections:
        if section.name.lower() in raw_text.lower():
            # Extract a quote from the section
            quote = section.content[:150].strip()
            citations.append(Citation(
                section=section.name,
                quote=quote,
                relevance=0.8,
            ))

    # Determine confidence
    if not citations:
        if "not covered" in raw_text.lower() or "not found" in raw_text.lower():
            confidence = ConfidenceLevel.NOT_FOUND
        else:
            confidence = ConfidenceLevel.LOW
    elif len(citations) >= 2:
        confidence = ConfidenceLevel.HIGH
    else:
        confidence = ConfidenceLevel.MEDIUM

    # Generate follow-up suggestions
    suggestions = _generate_follow_ups(question, document)

    return StructuredAnswer(
        answer=raw_text,
        citations=citations,
        confidence=confidence,
        follow_up_suggestions=suggestions,
    )


def _generate_follow_ups(question: str, document: ParsedDocument) -> list[str]:
    """Generate follow-up question suggestions based on document sections."""
    question_lower = question.lower()
    suggestions = []

    section_topics = {
        "compensation": "What are the overtime pay rules?",
        "benefits": "What health insurance options are available?",
        "time off": "How much PTO do employees get?",
        "security": "What are the data classification levels?",
        "fees": "What are the payment terms?",
        "sla": "What uptime guarantees are provided?",
        "api": "What are the API rate limits?",
        "revenue": "What is the revenue breakdown by segment?",
    }

    for topic, suggestion in section_topics.items():
        if topic not in question_lower:
            for section in document.sections:
                if topic in section.content.lower():
                    suggestions.append(suggestion)
                    break
        if len(suggestions) >= 3:
            break

    return suggestions
