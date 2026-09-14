"""
assistant.py -- Main multi-turn technical support assistant.

Ties together:
  - system_prompt.py: structured prompt with few-shot examples
  - context_manager.py: automatic pruning and compaction
  - subagent.py: isolated verbose lookups
  - structured_output.py: defensive response parsing

Can run in mock mode (default) or live mode (with API key).
"""

from __future__ import annotations

import json
import os
import sys
import time

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system_prompt import get_system_prompt
from context_manager import ContextManager, estimate_tokens
from structured_output import parse_response, AssistantResponse
from subagent import knowledge_base_lookup


# Keywords that trigger a knowledge base lookup
KB_TRIGGER_WORDS = [
    "how does", "how do", "what is", "explain", "tell me about",
    "documentation", "guide", "reference", "look up", "search",
    "auth", "database", "deploy", "api", "cache", "session",
    "oauth", "jwt", "redis", "postgres", "kubernetes", "ci/cd",
]


def _should_lookup(query: str) -> bool:
    """Decide whether a user query should trigger a knowledge base search."""
    query_lower = query.lower()
    return any(trigger in query_lower for trigger in KB_TRIGGER_WORDS)


def _generate_mock_response(query: str, kb_summary: str | None) -> str:
    """
    Generate a mock structured response.

    In mock mode, we produce valid JSON responses that follow the system prompt's
    format rules. This lets us test context management and parsing without API calls.
    """
    query_lower = query.lower()

    # Determine confidence based on query specificity
    if any(w in query_lower for w in ["specific", "exactly", "how do i"]):
        confidence = "high"
    elif any(w in query_lower for w in ["vague", "maybe", "something", "thing"]):
        confidence = "low"
    else:
        confidence = "medium"

    # Generate a topic-appropriate response
    if "auth" in query_lower or "login" in query_lower or "oauth" in query_lower:
        summary = "Authentication uses OAuth 2.0 with JWT tokens and supports MFA via TOTP or WebAuthn."
        details = ("The authentication system supports OAuth 2.0 (authorization_code, client_credentials, "
                   "refresh_token grants), SAML 2.0, and API key authentication. All flows require TLS 1.2+. "
                   "Sessions use JWT with RS256 signing, 1-hour access tokens, 30-day refresh tokens. "
                   "Rate limiting: 5 login attempts per minute per IP.")
        sources = ["Authentication System Documentation v3.2.1", "Security Guidelines"]
        follow_up = "Would you like details about API key rotation or MFA setup?"
    elif "database" in query_lower or "postgres" in query_lower or "query" in query_lower:
        summary = "PostgreSQL 16 with PgBouncer pooling, UUID primary keys, and continuous WAL archiving."
        details = ("Database stack: PostgreSQL 16 (primary), Redis 7.2 (cache), Elasticsearch 8.11 (search). "
                   "Connection pooling via PgBouncer in transaction mode (20 per instance, 100 total). "
                   "All tables use UUID PKs, soft deletes, and audit logging. Migrations via Flyway with "
                   "zero-downtime requirements. PITR available for 30 days, RTO 30min, RPO 5min.")
        sources = ["Database Architecture Guide v2.8.0", "Migration Standards"]
        follow_up = "Do you want to know about query performance optimization or backup procedures?"
    elif "deploy" in query_lower or "ci" in query_lower or "pipeline" in query_lower:
        summary = "Kubernetes on EKS with ArgoCD GitOps, canary deployments, and automatic rollback."
        details = ("CI/CD: GitHub Actions → Docker build → ArgoCD deploy. Stages: lint, test, build, "
                   "deploy-staging, smoke-test, deploy-prod. Rolling updates by default (maxSurge 25%). "
                   "Canary available: 5% traffic for 30min, auto-rollback on error rate >0.5%. "
                   "Monitoring: Prometheus + Grafana, OpenTelemetry traces, PagerDuty alerts.")
        sources = ["Deployment Pipeline Documentation v4.1.0", "Kubernetes Runbook"]
        follow_up = "Would you like details about rollback procedures or monitoring setup?"
    elif "api" in query_lower or "rest" in query_lower or "endpoint" in query_lower:
        summary = "REST API follows standard conventions with cursor pagination, structured errors, and URL versioning."
        details = ("API design: plural noun resources, max 2 nesting levels, cursor-based pagination "
                   "(max limit 100). Standard error format with error code, message, and details array. "
                   "Versioning: URL-based (/v1, /v2) with 6-month deprecation policy. "
                   "Methods: GET (read), POST (create, 201), PUT (replace), PATCH (partial), DELETE (204).")
        sources = ["REST API Design Standards v5.0.0", "API Style Guide"]
        follow_up = "Do you need specifics about error handling or pagination implementation?"
    elif "cache" in query_lower or "redis" in query_lower or "performance" in query_lower:
        summary = "Three-layer caching with Redis distributed cache, in-process cache, and CDN."
        details = ("Cache layers: L1 in-process (5min TTL, 1000 items), L2 Redis distributed "
                   "(configurable TTL), L3 CDN (CloudFront). Cache-aside pattern by default: "
                   "check cache → miss → query DB → store → return. Invalidation: event-driven "
                   "via pub/sub + TTL-based. Target hit rate >90%. Thundering herd protection via singleflight.")
        sources = ["Caching Strategy Guide v2.3.0", "Redis Operations Handbook"]
        follow_up = "Want to know about cache key design or invalidation strategies?"
    else:
        summary = "I can help with authentication, database, deployment, API design, or caching topics."
        details = ("I have documentation covering: (1) Authentication and authorization (OAuth, JWT, MFA), "
                   "(2) Database architecture (PostgreSQL, Redis, migrations), (3) Deployment and CI/CD "
                   "(Kubernetes, ArgoCD, canary), (4) REST API design standards, (5) Caching strategy "
                   "(Redis, CDN, invalidation). Please ask about a specific topic for detailed guidance.")
        sources = ["Technical Documentation Index"]
        confidence = "medium"
        follow_up = "What specific technical area would you like to explore?"

    # Add KB context if available
    if kb_summary:
        details += f"\n\nAdditional context from knowledge base: {kb_summary}"

    response = {
        "summary": summary,
        "details": details,
        "sources": sources,
        "confidence": confidence,
        "follow_up": follow_up,
    }

    time.sleep(0.03)  # Simulate API latency
    return json.dumps(response)


class TechSupportAssistant:
    """
    Multi-turn technical support assistant with context management.

    Demonstrates:
    1. System prompt with output constraints + few-shot examples
    2. Automatic context pruning and compaction
    3. Isolated verbose lookups (subagent pattern)
    4. Structured output with defensive parsing
    """

    def __init__(self, live_mode: bool = False):
        self.context = ContextManager()
        self.system_prompt = get_system_prompt()
        self.live_mode = live_mode
        self.client = None

        if live_mode:
            try:
                import anthropic
                self.client = anthropic.Anthropic()
            except Exception:
                print("    [No API key -- falling back to mock mode]")
                self.live_mode = False

    def ask(self, query: str) -> AssistantResponse:
        """
        Process a user query through the full pipeline.

        1. Check if KB lookup is needed
        2. If so, run isolated lookup and inject compact summary
        3. Build context-managed messages
        4. Get response (live or mock)
        5. Defensively parse the response
        6. Record metrics
        """
        # Step 1: Add user message
        self.context.add_user_message(query)

        # Step 2: Knowledge base lookup (isolated)
        kb_summary = None
        if _should_lookup(query):
            full_result, compact_summary = knowledge_base_lookup(query)
            # Only the compact summary enters conversation
            self.context.add_tool_output(compact_summary)
            kb_summary = compact_summary

        # Step 3: Get response
        if self.live_mode and self.client:
            raw_response = self._call_live(query)
        else:
            raw_response = _generate_mock_response(query, kb_summary)

        # Step 4: Defensive parsing
        parsed = parse_response(raw_response)

        # Step 5: Add assistant response to context
        self.context.add_assistant_message(raw_response)

        # Step 6: Record metrics
        self.context.record_turn_metrics(
            format_compliant=parsed.is_valid(),
            summary_word_count=parsed.summary_word_count(),
        )

        return parsed

    def _call_live(self, query: str) -> str:
        """Make a real API call with context-managed messages."""
        messages = self.context.get_messages_for_api()

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.0,
            system=self.system_prompt,
            messages=messages,
        )

        return response.content[0].text

    def get_turn_count(self) -> int:
        """Get current turn number."""
        return self.context.current_turn

    def get_metrics(self):
        """Get all recorded turn metrics."""
        return self.context.turn_metrics

    def get_context_report(self) -> str:
        """Get the context growth report."""
        return self.context.get_context_growth_report()

    def get_savings_report(self) -> dict:
        """Get token savings from pruning/compaction."""
        return self.context.get_token_savings_report()
