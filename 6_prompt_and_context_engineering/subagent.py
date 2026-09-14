"""
subagent.py -- Isolated verbose lookup (knowledge base search).

The subagent performs a "knowledge base search" that produces verbose raw data
(500-2000 tokens of documentation, API references, etc.).

KEY DESIGN: The raw result NEVER enters the main conversation history.
Only a compact summary (50-100 tokens) is injected. This prevents one
verbose lookup from consuming 10%+ of the context window.
"""

from __future__ import annotations

import time
from context_manager import estimate_tokens


# --------------------------------------------------------------------------
# Mock Knowledge Base -- simulates verbose documentation lookups
# --------------------------------------------------------------------------

KNOWLEDGE_BASE: dict[str, str] = {
    "authentication": """\
AUTHENTICATION AND AUTHORIZATION SYSTEM DOCUMENTATION (v3.2.1)

1. OVERVIEW
The authentication system supports OAuth 2.0, SAML 2.0, and API key-based authentication.
All authentication flows require TLS 1.2 or higher. Session tokens are JWT-based with
RS256 signing. Token lifetime defaults to 3600 seconds (1 hour) for access tokens and
2592000 seconds (30 days) for refresh tokens.

2. OAuth 2.0 IMPLEMENTATION
Supported grant types: authorization_code, client_credentials, refresh_token.
Authorization endpoint: /oauth/authorize
Token endpoint: /oauth/token
Revocation endpoint: /oauth/revoke
PKCE is required for public clients (SPA, mobile). Code verifier must be 43-128 characters.

3. API KEY AUTHENTICATION
API keys are scoped to specific permissions using a bitmask system.
Keys can be restricted by IP range (CIDR notation), rate limit tier, and expiration date.
Key rotation is supported via the /api-keys/rotate endpoint which issues a new key and
deprecates the old one after a 24-hour grace period.

4. SESSION MANAGEMENT
Sessions are stored in Redis with a TTL matching the access token lifetime.
Concurrent session limits can be configured per user role (default: 5 sessions).
Session invalidation propagates across all instances via Redis pub/sub within 500ms.

5. RATE LIMITING
Authentication endpoints are rate-limited separately from API endpoints.
Login attempts: 5 per minute per IP, 10 per minute per account.
Token refresh: 30 per hour per user.
API key validation: 1000 per minute per key.
Rate limit headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.

6. SECURITY CONSIDERATIONS
Passwords hashed with bcrypt (cost factor 12). MFA via TOTP (RFC 6238) or WebAuthn.
Failed login lockout: 5 failures trigger a 15-minute lockout with email notification.
Suspicious login detection based on: new IP, new device fingerprint, impossible travel.""",

    "database": """\
DATABASE ARCHITECTURE AND OPERATIONS GUIDE (v2.8.0)

1. DATABASE STACK
Primary: PostgreSQL 16 with logical replication
Cache: Redis 7.2 (cluster mode, 3 masters, 3 replicas)
Search: Elasticsearch 8.11 (3-node cluster)
Queue: PostgreSQL-based job queue (pg_boss) for background tasks

2. SCHEMA DESIGN PRINCIPLES
All tables use UUID primary keys (gen_random_uuid()).
Timestamps: created_at and updated_at on every table (UTC, timestamptz).
Soft deletes via deleted_at column (nullable timestamptz).
Audit trail: all mutations logged to audit_log table with user_id, action, old/new values.

3. CONNECTION MANAGEMENT
Connection pooler: PgBouncer in transaction mode.
Pool sizes: 20 connections per application instance, max 100 total.
Idle connection timeout: 300 seconds. Statement timeout: 30 seconds (configurable).
Connection string format: postgresql://user:pass@pgbouncer:6432/dbname?sslmode=require

4. QUERY PERFORMANCE
All queries must be reviewed for: sequential scans on tables >10K rows, missing indexes,
N+1 patterns, excessive JOINs (max 4 tables recommended).
Use EXPLAIN ANALYZE for any query taking >100ms.
Partial indexes recommended for: boolean columns, status fields, date ranges.

5. MIGRATION STRATEGY
Migrations managed by Flyway. Naming: V{version}__{description}.sql.
Zero-downtime migrations only. No DROP COLUMN in production (use deprecation period).
Large table migrations use pt-online-schema-change pattern.
Rollback scripts required for every migration.

6. BACKUP AND RECOVERY
Continuous WAL archiving to S3 (every 5 minutes).
Full base backup: daily at 02:00 UTC.
Point-in-time recovery (PITR) available for last 30 days.
RTO: 30 minutes. RPO: 5 minutes.
Monthly recovery drill (restore to staging and validate).""",

    "deployment": """\
DEPLOYMENT AND CI/CD PIPELINE DOCUMENTATION (v4.1.0)

1. INFRASTRUCTURE
Cloud: AWS (us-east-1 primary, eu-west-1 DR)
Orchestration: Kubernetes (EKS) with Karpenter for auto-scaling
Container registry: ECR with vulnerability scanning
Infrastructure as Code: Terraform with remote state in S3

2. CI/CD PIPELINE
Source: GitHub with branch protection rules
CI: GitHub Actions with parallel test execution
Build: Docker multi-stage builds (builder + runtime images)
Deploy: ArgoCD with GitOps workflow
Stages: lint → unit-test → integration-test → build → deploy-staging → smoke-test → deploy-prod

3. DEPLOYMENT STRATEGIES
Default: Rolling update (maxSurge: 25%, maxUnavailable: 0)
Feature flags: LaunchDarkly for gradual rollouts
Canary: 5% traffic for 30 minutes, auto-rollback on error rate >0.5%
Blue/green: Available for database-breaking changes (manual trigger)

4. MONITORING AND ALERTING
Metrics: Prometheus + Grafana (custom dashboards per service)
Logs: Structured JSON → Fluent Bit → Elasticsearch → Kibana
Traces: OpenTelemetry → Jaeger (sampling rate: 10% in production)
Alerts: PagerDuty integration with escalation policies
SLOs: 99.9% availability, P99 latency <500ms, error rate <0.1%

5. ROLLBACK PROCEDURES
Automatic rollback if: health check fails within 5 minutes of deploy,
error rate exceeds 2x baseline, P99 latency exceeds 3x baseline.
Manual rollback: ArgoCD sync to previous Git commit (takes ~2 minutes).
Database rollback: apply reverse migration within 1 hour of deploy.""",

    "api_design": """\
REST API DESIGN STANDARDS AND CONVENTIONS (v5.0.0)

1. URL STRUCTURE
Base URL: https://api.example.com/v{major}
Resources: plural nouns (e.g., /users, /orders, /products)
Nested resources: max 2 levels deep (e.g., /users/{id}/orders)
Query parameters for filtering, sorting, pagination

2. HTTP METHODS
GET: read (idempotent, cacheable)
POST: create (returns 201 + Location header)
PUT: full replace (idempotent)
PATCH: partial update (accepts JSON Merge Patch, RFC 7386)
DELETE: remove (idempotent, returns 204)

3. PAGINATION
Default: cursor-based pagination for large collections
Params: ?cursor=abc&limit=20 (max limit: 100)
Response headers: Link (rel=next, rel=prev), X-Total-Count
Offset pagination available via ?offset=0&limit=20 (discouraged for large datasets)

4. ERROR RESPONSES
Standard format: {"error": {"code": "ERROR_CODE", "message": "Human-readable", "details": [...]}}
HTTP 400: validation errors with per-field detail
HTTP 401: authentication required
HTTP 403: insufficient permissions (include required permission)
HTTP 404: resource not found
HTTP 409: conflict (include current state)
HTTP 429: rate limited (include Retry-After header)
HTTP 500: internal error (log correlation ID, return to client)

5. VERSIONING
URL-based versioning: /v1, /v2
Breaking changes require new major version
Deprecation policy: 6 months notice, sunset header in responses
Version discovery: GET /versions returns supported versions and sunset dates""",

    "caching": """\
CACHING STRATEGY AND IMPLEMENTATION GUIDE (v2.3.0)

1. CACHE LAYERS
L1: In-process cache (node-cache, 5-minute TTL, 1000 items max)
L2: Redis distributed cache (configurable TTL per key pattern)
L3: CDN cache (CloudFront, static assets + API responses with Cache-Control)
Database: PostgreSQL materialized views (refreshed every 15 minutes)

2. CACHE KEY DESIGN
Pattern: {service}:{resource}:{identifier}:{version}
Examples: users:profile:uuid-123:v2, products:list:category-electronics:page-1
Hash long keys with SHA-256 if >250 characters
Include API version in cache key to prevent stale data across deployments

3. CACHE INVALIDATION
Event-driven: publish CacheInvalidation event on mutations
Pattern-based: invalidate by prefix (e.g., users:profile:uuid-123:*)
Time-based: TTL per resource type (user profiles: 5min, product catalog: 1hr)
Manual: admin endpoint /cache/invalidate with pattern parameter

4. CACHE-ASIDE PATTERN (DEFAULT)
Read: check cache → if miss, query DB → store in cache → return
Write: update DB → invalidate cache (do NOT update cache, to avoid race conditions)
Thundering herd protection: use singleflight/coalescing on cache misses

5. PERFORMANCE METRICS
Target cache hit rate: >90% for read-heavy endpoints
Monitor: hit rate, miss rate, eviction rate, memory usage
Alert: hit rate drops below 80% or eviction rate exceeds 100/minute""",
}

# Topics that don't have KB entries -- used to test "no results" handling
NO_RESULT_TOPICS = {"quantum computing", "cooking recipes", "philosophy"}


def knowledge_base_lookup(query: str) -> tuple[str, str]:
    """
    Perform a verbose knowledge base search.

    This simulates what a real RAG system or documentation search would produce:
    a large block of raw text that's useful but far too verbose for a conversation.

    Returns:
        (full_result, compact_summary)
        - full_result: the raw verbose output (500+ tokens) -- for logging only
        - compact_summary: what gets injected into conversation (50-100 tokens)
    """
    query_lower = query.lower()

    # Find matching KB entry
    best_match = None
    best_score = 0

    for topic, content in KNOWLEDGE_BASE.items():
        # Simple keyword matching
        topic_words = topic.replace("_", " ").split()
        score = sum(1 for w in topic_words if w in query_lower)

        # Also check for related keywords
        content_words = content.lower()
        keyword_hits = sum(1 for word in query_lower.split()
                          if len(word) > 3 and word in content_words)
        score += keyword_hits * 0.5

        if score > best_score:
            best_score = score
            best_match = (topic, content)

    if best_match is None or best_score < 0.5:
        full_result = f"No knowledge base entries found for query: '{query}'"
        compact_summary = f"[KB Search: '{query}'] No relevant documentation found."
        return full_result, compact_summary

    topic, content = best_match

    # Full result (verbose -- this is what a real RAG would return)
    full_result = content

    # Compact summary (this is what goes into conversation)
    # Take the first section heading + first 2-3 key points
    lines = content.strip().split("\n")
    title = lines[0] if lines else topic
    key_points = []
    for line in lines[1:]:
        line = line.strip()
        if line and not line.startswith(("1.", "2.", "3.", "4.", "5.", "6.")) and len(line) > 20:
            key_points.append(line.split(".")[0].strip())
            if len(key_points) >= 3:
                break

    compact_summary = (
        f"[KB Search: '{query}'] Found: {title}. "
        f"Key topics: {'; '.join(key_points[:3]) if key_points else 'See full documentation'}. "
        f"({estimate_tokens(content)} tokens in full doc, {estimate_tokens(title)} in summary)"
    )

    # Simulate lookup latency
    time.sleep(0.02)

    return full_result, compact_summary


def get_kb_stats() -> dict:
    """Return knowledge base statistics."""
    return {
        "topics": list(KNOWLEDGE_BASE.keys()),
        "total_entries": len(KNOWLEDGE_BASE),
        "total_tokens": sum(estimate_tokens(v) for v in KNOWLEDGE_BASE.values()),
        "avg_tokens_per_entry": sum(estimate_tokens(v) for v in KNOWLEDGE_BASE.values()) // len(KNOWLEDGE_BASE),
    }
