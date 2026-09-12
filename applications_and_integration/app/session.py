"""
app/session.py -- Session manager with explicit lifecycle decisions.

SESSION DESIGN DECISIONS (required by assignment)
===================================================

1. WHEN TO CREATE A SESSION:
   A new session is created each time a document is uploaded. The session_id
   is a UUID returned to the client. One session = one document + its
   conversation history. Rationale: users think in terms of "I'm working on
   this document right now," so the session boundary matches the document.

2. WHEN TO PERSIST:
   Sessions are stored in-memory (a dict). In production, this would be
   Redis or a database, but the interface is identical -- swap the storage
   backend without changing the API. We persist on every write (question +
   answer appended to history). Rationale: losing a turn mid-conversation
   is worse than the cost of a write.

3. WHEN TO SUMMARIZE:
   When the conversation history exceeds `summarize_threshold` tokens
   (estimated at ~4 chars/token), older turns are collapsed into a single
   summary message. This keeps the context window manageable while
   preserving conversational continuity. Rationale: prompt caching already
   handles the document cost -- summarization targets the growing
   conversation tail.

4. WHEN TO RESTART:
   - Explicit: client calls POST /sessions/{id}/reset
   - Implicit: client uploads a new document to the same session (not
     implemented -- we create a new session instead, which is simpler and
     less error-prone)
   Rationale: explicit restarts are safer. Implicit restarts risk data loss
   if the user didn't mean to replace the document.

5. WHEN TO EXPIRE:
   Sessions expire after `idle_timeout_minutes` (default 30 min) of
   inactivity. A background cleanup would run periodically in production;
   here we check on access. Rationale: sessions accumulate memory. Without
   expiry, a busy server's memory grows unbounded.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.config import get_session_config
from app.document import ParsedDocument


@dataclass
class ConversationTurn:
    """A single question-answer exchange."""
    question: str
    answer: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Session:
    """A document Q&A session with conversation history."""
    session_id: str
    document: ParsedDocument
    history: list[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_summarized: bool = False
    _summary: Optional[str] = None

    def add_turn(self, question: str, answer: str) -> None:
        """Record a conversation turn and update activity timestamp."""
        self.history.append(ConversationTurn(question=question, answer=answer))
        self.last_activity = datetime.now()

    def get_messages_for_api(self) -> list[dict]:
        """
        Build the messages array for the Anthropic API.

        If the conversation has been summarized, the first message is the
        summary of older turns, followed by recent turns.
        """
        messages = []

        if self._summary:
            # Include summary of older turns as context
            messages.append({
                "role": "user",
                "content": f"[Previous conversation summary: {self._summary}]",
            })
            messages.append({
                "role": "assistant",
                "content": "Understood. I have the context from our previous conversation.",
            })

        for turn in self.history:
            messages.append({"role": "user", "content": turn.question})
            messages.append({"role": "assistant", "content": turn.answer})

        return messages

    def estimate_history_tokens(self) -> int:
        """
        Estimate the token count of the conversation history.
        Uses ~4 chars per token as a rough heuristic.
        """
        total_chars = sum(
            len(t.question) + len(t.answer) for t in self.history
        )
        if self._summary:
            total_chars += len(self._summary)
        return total_chars // 4

    def needs_summarization(self) -> bool:
        """Check if history has grown past the summarization threshold."""
        config = get_session_config()
        return self.estimate_history_tokens() > config.get("summarize_threshold", 40000)

    def summarize_history(self) -> None:
        """
        Collapse older turns into a summary, keeping only the last 3 turns.

        In live mode, this would call Claude to generate the summary.
        In mock mode, we create a simple concatenation.
        """
        if len(self.history) <= 3:
            return  # Not enough turns to summarize

        # Keep the last 3 turns as active history
        older = self.history[:-3]
        recent = self.history[-3:]

        # Build summary from older turns
        summary_parts = []
        for turn in older:
            summary_parts.append(
                f"Q: {turn.question[:100]}... A: {turn.answer[:150]}..."
            )
        self._summary = " | ".join(summary_parts)
        self.history = recent
        self.is_summarized = True

    def reset_conversation(self) -> None:
        """Reset the conversation but keep the document."""
        self.history = []
        self._summary = None
        self.is_summarized = False
        self.last_activity = datetime.now()

    def is_expired(self) -> bool:
        """Check if the session has expired due to inactivity."""
        config = get_session_config()
        timeout = timedelta(minutes=config.get("idle_timeout_minutes", 30))
        return datetime.now() - self.last_activity > timeout


class SessionManager:
    """
    In-memory session store.

    Production upgrade path: Replace with Redis-backed implementation for:
    1. Multi-worker safety (this dict is NOT thread/process safe)
    2. Persistence across restarts
    3. Distributed session access across multiple server instances
    The interface (create, get, delete, reset) stays the same.

    Code review fix: documented thread-safety limitation (Issue #1, HIGH).
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(self, document: ParsedDocument) -> Session:
        """Create a new session for a document."""
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id, document=document)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.
        Returns None if the session doesn't exist or has expired.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired():
            # Clean up expired session
            del self._sessions[session_id]
            return None
        return session

    def reset_session(self, session_id: str) -> Optional[Session]:
        """Reset a session's conversation, keeping the document."""
        session = self.get_session(session_id)
        if session:
            session.reset_conversation()
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session entirely."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[Session]:
        """List all active (non-expired) sessions."""
        # Clean up expired sessions
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            del self._sessions[sid]
        return list(self._sessions.values())
