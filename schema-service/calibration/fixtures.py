"""Fixture catalogue for the calibration harness.

Each fixture provides a realistic SDD context string for one of the 6 phases,
labelled by complexity: simple, medium, or complex.

Token validation uses tiktoken cl100k_base, which is an approximation — not
billing-accurate for every model, but stable across runs (suitable for a
relative-delta harness).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import tiktoken

Phase = Literal["propose", "spec", "design", "tasks", "verify", "explore", "apply"]
Difficulty = Literal["simple", "medium", "complex"]

MAX_TOKENS = 28_000

_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True)
class Fixture:
    id: str
    phase: Phase
    difficulty: Difficulty
    context: str
    payload_extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        token_count = len(_ENCODING.encode(self.context))
        if token_count > MAX_TOKENS:
            raise ValueError(
                f"Fixture '{self.id}' exceeds {MAX_TOKENS} token limit "
                f"({token_count} tokens)."
            )


# ---------------------------------------------------------------------------
# Fixture catalogue
# ---------------------------------------------------------------------------

FIXTURES: dict[Phase, list[Fixture]] = {
    "propose": [
        Fixture(
            id="propose-simple-01",
            phase="propose",
            difficulty="simple",
            context=(
                "Add a dark mode toggle to the user settings page. "
                "The app currently uses a light theme defined in a single CSS file. "
                "Users have requested the ability to switch between light and dark modes. "
                "The toggle should persist across sessions using localStorage."
            ),
        ),
        Fixture(
            id="propose-medium-01",
            phase="propose",
            difficulty="medium",
            context=(
                "Introduce rate limiting on the public REST API. "
                "Currently there are no rate limits. We have reports of scrapers "
                "hitting /search at 200 req/s causing elevated LLM costs. "
                "We use FastAPI with Redis already deployed for session storage. "
                "We need per-IP limits with a 429 response and Retry-After header. "
                "Authenticated users should get a higher quota than anonymous ones."
            ),
        ),
        Fixture(
            id="propose-complex-01",
            phase="propose",
            difficulty="complex",
            context=(
                "Migrate the user authentication system from session-based auth to "
                "JWT-based stateless auth. The current system uses server-side sessions "
                "stored in PostgreSQL. We have ~50k active users, a mobile app, and two "
                "third-party integrations that call our API. We need to support refresh "
                "tokens, token revocation for logout, and a migration path that does not "
                "force all users to re-login simultaneously. The system must remain "
                "backwards-compatible for 30 days during the transition period."
            ),
        ),
    ],
    "spec": [
        Fixture(
            id="spec-simple-01",
            phase="spec",
            difficulty="simple",
            context=(
                "Proposal: Add email notifications for new comments on a user's post. "
                "Intent: Allow post authors to receive an email when someone comments. "
                "Scope in: email on new comment, unsubscribe link. "
                "Scope out: push notifications, SMS, in-app notifications. "
                "Risks: email deliverability, spam. "
                "Next steps: pick transactional email provider, implement webhook."
            ),
        ),
        Fixture(
            id="spec-medium-01",
            phase="spec",
            difficulty="medium",
            context=(
                "Proposal: Introduce a feature flag system to enable gradual rollouts. "
                "Intent: Allow product and engineering to toggle features per user cohort "
                "without code deployments. Scope in: flag CRUD, percentage-based rollout, "
                "user-segment targeting, admin UI. Scope out: A/B testing stats, "
                "multi-variate experiments. Risks: flag explosion, stale flags, "
                "performance overhead of flag evaluation at request time. "
                "Next steps: evaluate LaunchDarkly vs homegrown, design the flag schema."
            ),
        ),
        Fixture(
            id="spec-complex-01",
            phase="spec",
            difficulty="complex",
            context=(
                "Proposal: Add multi-tenant support to the SaaS platform. "
                "Each tenant must have isolated data (row-level security in Postgres), "
                "custom subdomain routing, per-tenant billing, and the ability to invite "
                "team members with role-based access control (owner, admin, member). "
                "Intent: unlock B2B sales. Scope in: tenant provisioning, RBAC, "
                "subdomain routing, billing hooks. Scope out: white-labelling, "
                "tenant-specific SLAs, on-premise deployment. Risks: data isolation "
                "bugs, RLS policy gaps, cross-tenant query leaks, billing edge cases."
            ),
        ),
    ],
    "design": [
        Fixture(
            id="design-simple-01",
            phase="design",
            difficulty="simple",
            context=(
                "Spec: Implement a CSV export endpoint for the admin dashboard. "
                "Requirements: GET /admin/export?resource=users returns a CSV with all "
                "user rows. Fields: id, email, created_at, plan. Scenarios: empty table "
                "returns header-only CSV; large table streams response. "
                "Out of scope: filtering, pagination, XLS format."
            ),
        ),
        Fixture(
            id="design-medium-01",
            phase="design",
            difficulty="medium",
            context=(
                "Spec: Background job queue for sending transactional emails. "
                "Requirements: enqueue a job with {to, subject, body_html}; worker "
                "processes jobs with at-least-once delivery; failed jobs retry up to 3 "
                "times with exponential backoff; dead-letter queue for permanently failed "
                "jobs; admin endpoint to inspect DLQ. Scenarios: happy path, retry "
                "exhaustion, DLQ inspection. Out of scope: scheduling, batch sends, "
                "template rendering."
            ),
        ),
        Fixture(
            id="design-complex-01",
            phase="design",
            difficulty="complex",
            context=(
                "Spec: Real-time collaborative document editing. "
                "Requirements: multiple users editing the same document concurrently; "
                "changes merge without conflicts using CRDT (Yjs); presence indicators "
                "show active cursors; document state persists to PostgreSQL on every "
                "N operations or 5-second idle; offline edits sync on reconnect. "
                "Scenarios: two-user concurrent edit, network partition recovery, "
                "500-user load test. Out of scope: version history, comments, "
                "access-control changes."
            ),
        ),
    ],
    "tasks": [
        Fixture(
            id="tasks-simple-01",
            phase="tasks",
            difficulty="simple",
            context=(
                "Design: Add a /health endpoint to the FastAPI application. "
                "Approach: single GET /health route returning {status: ok, version: str}. "
                "Decisions: no auth required, no DB check for the basic endpoint. "
                "File changes: app/routes/health.py (create), app/main.py (register). "
                "Testing strategy: unit test with TestClient asserting 200 + JSON body."
            ),
        ),
        Fixture(
            id="tasks-medium-01",
            phase="tasks",
            difficulty="medium",
            context=(
                "Design: Implement pagination for the /posts list endpoint. "
                "Approach: cursor-based pagination using created_at + id composite key. "
                "Decisions: page_size max 100, default 20; cursor is a base64-encoded "
                "JSON string; no total_count (avoids COUNT(*) on large tables). "
                "File changes: app/routes/posts.py (modify), app/schemas/posts.py "
                "(add CursorPage model), tests/test_posts.py (extend). "
                "Testing strategy: unit tests for cursor encode/decode; integration "
                "test with 50 seeded rows asserting correct page boundaries."
            ),
        ),
        Fixture(
            id="tasks-complex-01",
            phase="tasks",
            difficulty="complex",
            context=(
                "Design: Introduce an event sourcing layer for the order management "
                "domain. Approach: append-only events table; projections rebuilt from "
                "events; commands validated against current projection state; snapshots "
                "every 100 events to bound replay time. Decisions: PostgreSQL as event "
                "store (no Kafka for now); projection rebuild is synchronous on startup; "
                "snapshot table co-located with events. File changes: "
                "app/events/ (new module), app/projections/ (new module), "
                "app/commands/ (new module), migrations/ (3 new files), "
                "tests/test_events.py, tests/test_projections.py. "
                "Testing strategy: property-based tests for event replay determinism; "
                "integration tests for command/projection round-trip."
            ),
        ),
    ],
    "verify": [
        Fixture(
            id="verify-simple-01",
            phase="verify",
            difficulty="simple",
            context=(
                "Spec required: POST /v1/login returns 200 with {token: str} on valid "
                "credentials and 401 on invalid. Implementation: routes/auth.py handles "
                "the endpoint, hashes password with bcrypt, returns a signed JWT. "
                "Tests: test_auth.py covers happy path and wrong password. "
                "Please verify implementation against spec."
            ),
        ),
        Fixture(
            id="verify-medium-01",
            phase="verify",
            difficulty="medium",
            context=(
                "Spec required: The search endpoint must support fuzzy matching, "
                "return results sorted by relevance score, and respond within 200ms "
                "for queries under 100 results. Implementation uses PostgreSQL full-text "
                "search with ts_rank. Tests cover accuracy but not latency. "
                "The 200ms SLA has no load test or benchmark. "
                "Please verify implementation against spec."
            ),
        ),
        Fixture(
            id="verify-complex-01",
            phase="verify",
            difficulty="complex",
            context=(
                "Spec required: Multi-tenant data isolation using Postgres row-level "
                "security. Every table in the tenants schema must have an RLS policy "
                "enforcing tenant_id = current_setting('app.tenant_id'). "
                "Implementation: RLS policies added to users and posts tables only. "
                "The payments and audit_log tables have no RLS. Migrations were written "
                "but the SET ROLE statement is missing from the connection setup. "
                "Tests assert correct isolation for users but do not test payments. "
                "Please verify implementation against spec and flag gaps."
            ),
        ),
    ],
    "explore": [
        Fixture(
            id="explore-simple-01",
            phase="explore",
            difficulty="simple",
            context=(
                "I want to add server-side caching to the GET /products endpoint. "
                "The endpoint currently queries PostgreSQL on every request. "
                "Traffic is ~500 req/min and the product catalogue changes infrequently "
                "(at most once per hour). The stack is FastAPI + SQLAlchemy + Redis. "
                "Please explore caching options and trade-offs."
            ),
        ),
        Fixture(
            id="explore-medium-01",
            phase="explore",
            difficulty="medium",
            context=(
                "We want to replace the current synchronous PDF generation (weasyprint, "
                "blocking the request thread for 2-8 seconds) with an async approach. "
                "The app is FastAPI. We generate ~200 PDFs/day, peak 20 concurrent. "
                "PDFs are user-triggered from the UI and must be downloadable within "
                "30 seconds. Explore options including Celery, ARQ, and native asyncio "
                "offloading, and their trade-offs around reliability and complexity."
            ),
        ),
        Fixture(
            id="explore-complex-01",
            phase="explore",
            difficulty="complex",
            context=(
                "We need to migrate 10 years of customer data (150M rows across 40 "
                "tables) from a legacy MySQL 5.7 schema to a new PostgreSQL 16 schema "
                "with a normalised design. The application cannot have more than 4 hours "
                "of downtime. Some tables have no primary keys. Foreign key relationships "
                "are enforced at the application layer only. Explore strategies for the "
                "migration: dual-write, shadow table, pg_loader, and custom ETL. "
                "Consider data validation, rollback, and the 4-hour downtime constraint."
            ),
        ),
    ],
    "apply": [
        Fixture(
            id="apply-simple-01",
            phase="apply",
            difficulty="simple",
            context="Add a dark mode toggle to the settings page, persisted via localStorage.",
            payload_extra={
                "tasks": [
                    "Add toggleDarkMode() function to app/utils/theme.py",
                    "Persist preference to localStorage in frontend/settings.js",
                ]
            },
        ),
        Fixture(
            id="apply-medium-01",
            phase="apply",
            difficulty="medium",
            context="Implement a rate limiter middleware for the /api/search endpoint. Spec: max 60 req/min per IP, return 429 with Retry-After header, store counters in Redis with TTL=60s.",
            payload_extra={
                "tasks": [
                    "Create app/middleware/rate_limiter.py with RateLimiter class using Redis INCR + EXPIRE",
                    "Register middleware in app/main.py only for routes prefixed /api/search",
                    "Return HTTP 429 with Retry-After: 60 header when limit exceeded",
                    "Add unit tests in tests/test_rate_limiter.py covering: under-limit, at-limit, over-limit, TTL reset",
                ]
            },
        ),
        Fixture(
            id="apply-complex-01",
            phase="apply",
            difficulty="complex",
            context="Migrate the user authentication system from session-based to JWT. Requirements: access token (15min TTL), refresh token (7d TTL, stored in httpOnly cookie), token rotation on refresh, revocation list in Redis, backward-compatible for 30 days (accept both session and JWT).",
            payload_extra={
                "tasks": [
                    "Create app/auth/jwt.py: generate_access_token(), generate_refresh_token(), verify_token()",
                    "Create app/auth/revocation.py: RevocationStore backed by Redis SET with TTL",
                    "Update POST /auth/login to issue both tokens; set refresh in httpOnly cookie",
                    "Create POST /auth/refresh: verify refresh token, check revocation list, rotate tokens",
                    "Create POST /auth/logout: add refresh token to revocation list",
                    "Add JWT verification middleware in app/middleware/auth.py; fall back to session auth if JWT absent",
                    "Update tests/test_auth.py: cover login, refresh rotation, logout revocation, expired token rejection",
                ]
            },
        ),
    ],
}


def get_fixtures(phase: Phase) -> list[Fixture]:
    """Return all fixtures for the given phase.

    Raises KeyError if the phase is not in the catalogue.
    """
    return FIXTURES[phase]
