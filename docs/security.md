# Security Model

This document describes AgentGuard's security architecture as it is actually implemented, including its known limitations.

---

## Authentication

### Dashboard Users (JWT)

Human users authenticate via `POST /api/v1/auth/login` and receive a JWT access token:

- **Algorithm:** HS256
- **Secret:** `JWT_SECRET` environment variable
- **Expiration:** 30 minutes (configured as `ACCESS_TOKEN_EXPIRE_MINUTES` in `security/jwt.py`)
- **Claims:** `sub` (user UUID), `organization_id`, `role`

**Known limitation: No refresh tokens.** When the access token expires, the user must re-authenticate with email and password. There is no silent token refresh mechanism. This is a deliberate simplification — a production deployment would need refresh token rotation.

**Known limitation: No password reset.** The system has no forgot-password flow, no email verification, and no account recovery mechanism.

### Agent Authentication (API Keys)

Autonomous agents authenticate via the `X-API-Key` header (or as a Bearer token starting with `ag_`):

- **Format:** `ag_live_` prefix + random hex string
- **Storage:** SHA-256 hashed in the `api_keys` table. The plaintext key is shown **exactly once** at creation and is never stored.
- **Binding:** Each API key is bound to an `organization_id` and optionally to an `agent_id`.
- **Expiration:** Optional `expires_at` timestamp, checked on every request.
- **Revocation:** Setting `is_active=false`. Revoked keys are rejected immediately.

### Password Hashing

User passwords are hashed with **bcrypt** via the `passlib` library. Plaintext passwords are never stored.

### Google OAuth 2.0 ("Continue with Google")

AgentGuard supports Google OAuth 2.0 Authorization Code flow for human dashboard users:

#### Flow Summary

1. `GET /api/v1/auth/google/login` — generates a cryptographically signed CSRF `state` JWT (HS256, 10-minute expiry) and redirects to Google's authorization endpoint with `email` and `profile` scopes.
2. Google authenticates the user and redirects to `GOOGLE_REDIRECT_URI` (`GET /api/v1/auth/google/callback`).
3. The callback validates the `state` JWT first (CSRF protection — any tampered or expired `state` immediately redirects to `/login?error=invalid_or_expired_state`).
4. The `code` is exchanged for Google tokens via `https://oauth2.googleapis.com/token`.
5. The Google **ID token** is verified for:
   - Signature (via Google's public key endpoint)
   - `aud` audience (must match `GOOGLE_CLIENT_ID` exactly)
   - Token expiry
6. The verified email is looked up globally (not per-org) in the `users` table. If no account exists, one is auto-provisioned with a new organization and ADMIN role.
7. A **one-time, 60-second opaque exchange code** is generated and placed in the redirect URL (`?code=<exchange_code>`) to the frontend.
8. The frontend calls `POST /api/v1/auth/google/exchange` to exchange the code for the actual JWT access token.

#### Security Properties of This Design

| Property | How Enforced |
|----------|--------------|
| **CSRF protection** | Signed `state` JWT verified before any code exchange. Tampered or expired state → immediate error redirect, no code consumed. |
| **JWT never in URL** | The redirect URL contains only a short-lived opaque exchange code, not the JWT. This prevents the token appearing in browser history, Referer headers, or server access logs. |
| **Single-use code** | The exchange code is consumed atomically from an in-process store. Any second use returns 400, preventing replay attacks. |
| **ID token verification** | Google ID token signature and `aud` (audience) are verified before any user is resolved. A token from a different Google project cannot authenticate. |
| **Email uniqueness** | User identity is globally unique on `email` (enforced via `UNIQUE` constraint across all organizations). A user with the same email cannot create duplicate accounts via OAuth vs. email/password. |
| **`hashed_password` nullable** | Google-only accounts have `hashed_password = NULL`. They cannot log in via the email/password endpoint — no password guessing is possible because no password exists. |

#### Google Cloud Console Requirements

For Google OAuth to function:
- The `GOOGLE_REDIRECT_URI` value must be listed in **Authorized redirect URIs** in the OAuth client configuration.
- The production frontend origin must be listed in **Authorized JavaScript origins**.
- The OAuth consent screen must be **Published** (not in Testing mode) before non-test users can sign in. In Testing mode, only users explicitly added as test users are permitted.

---

## Global Email Uniqueness

The `users.email` column has a `UNIQUE` constraint across the entire table (not scoped per organization). This was a deliberate architectural decision, introduced in Alembic migration `3f8a9e1b2c4d_make_email_globally_unique.py`.

**Rationale:** Google ID tokens identify users by their verified email address. If email were only unique per-organization, a user with `alice@gmail.com` could create two accounts — one via email/password in Org A, and one via Google OAuth in Org B. When Alice later tried "Continue with Google", the system would have no safe way to resolve which account to use. Global uniqueness means one real person always maps to exactly one account, and the OAuth and email/password flows are mutually exclusive for the same email.

**Consequence:** An organization cannot have two users with the same email across the system. This is acceptable for the current single-tenant-per-deployment use case.

---

## `hitl_requests.reviewer_id` ON DELETE RESTRICT

The `hitl_requests.reviewer_id` foreign key (referencing `users.id`) uses `ON DELETE RESTRICT`, introduced in Alembic migration `4a7b2c9d1e3f_restrict_user_fk_on_hitl_requests.py`.

**Rationale:** An `ON DELETE CASCADE` or `SET NULL` would silently destroy the audit trail of who approved or denied a high-risk action. Knowing which human reviewed a pending HITL request is part of the evidentiary record. The `RESTRICT` constraint means you cannot delete a user who has reviewed HITL requests, preserving audit integrity. Deleting such a user requires archiving or re-assigning the reviews first.

Every authenticated user has exactly one role within their organization. The following matrix shows which roles can access which endpoints, as enforced by the `require_role()` dependency in the actual route handlers:

| Endpoint | ADMIN | SECURITY | AUDITOR | MANAGER | DEVELOPER |
|----------|:-----:|:--------:|:-------:|:-------:|:---------:|
| **Agents** | | | | | |
| POST /agents (create) | ✓ | ✓ | | | ✓ |
| GET /agents (list/read) | ✓ | ✓ | ✓ | ✓ | ✓ |
| PATCH /agents (update) | ✓ | ✓ | | | |
| DELETE /agents (soft delete) | ✓ | ✓ | | | |
| **Tools** | | | | | |
| POST /tools (create) | ✓ | ✓ | | | ✓ |
| GET /tools (list/read) | ✓ | ✓ | ✓ | ✓ | ✓ |
| PATCH /tools (update) | ✓ | ✓ | | | |
| **Permissions** | | | | | |
| POST /permissions (grant) | ✓ | ✓ | | | |
| DELETE /permissions (revoke) | ✓ | ✓ | | | |
| GET /permissions (list) | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Policies** | | | | | |
| POST /policies (create) | ✓ | ✓ | | | |
| GET /policies (list/read) | ✓ | ✓ | ✓ | ✓ | |
| PATCH /policies (update) | ✓ | ✓ | | | |
| DELETE /policies (soft delete) | ✓ | ✓ | | | |
| **Budgets** | | | | | |
| GET /budgets (list) | ✓ | ✓ | ✓ | ✓ | |
| PATCH /budgets (update) | ✓ | ✓ | | | |
| **HITL** | | | | | |
| GET /hitl (list) | ✓ | | | ✓ | |
| GET /hitl/{id} | ✓ | | | ✓ | |
| POST /hitl/{id}/approve | ✓ | | | ✓ | |
| POST /hitl/{id}/deny | ✓ | | | ✓ | |
| **Audit Vault** | | | | | |
| GET /audit (list) | ✓ | | ✓ | | |
| GET /audit/{id} | ✓ | | ✓ | | |
| POST /audit/verify | ✓ | | ✓ | | |
| **Guard** | | | | | |
| POST /guard/check | API Key only (agents) | | | | |
| **Auth** | | | | | |
| POST /auth/register | Public | | | | |
| POST /auth/login | Public | | | | |
| GET /auth/google/login | Public | | | | |
| GET /auth/google/callback | Public | | | | |
| POST /auth/google/exchange | Public | | | | |
| GET /auth/me | Any authenticated | | | | |
| POST /auth/api-keys | Any authenticated | | | | |
| GET /auth/api-keys | Any authenticated | | | | |
| DELETE /auth/api-keys/{id} | Any authenticated | | | | |

### RBAC Enforcement Implementation

RBAC is enforced via FastAPI dependency injection, not route-level middleware:

```python
# In each route handler:
current_user: AuthenticatedUser = Depends(require_role(RoleEnum.ADMIN, RoleEnum.SECURITY))
```

The `require_role()` factory returns a dependency that:
1. Extracts the JWT from the `Authorization: Bearer` header
2. Decodes and validates the token
3. Loads the user from the database
4. Checks the user's role against the allowed set
5. Returns HTTP 403 if the role is not permitted

---

## Organization Isolation

Every data-bearing table has an `organization_id` foreign key. Every repository query is scoped by the caller's `organization_id`, which is extracted from:
- The JWT claims (for dashboard users)
- The API key record (for agents)

There is no endpoint that allows cross-organization data access. This isolation is enforced at the repository layer, making it structural rather than policy-based.

---

## CRITICAL-Risk Override Invariant

This is the most important safety invariant in the system:

> **A CRITICAL-risk tool is always denied by the policy engine, regardless of whether the agent has an explicit permission grant.**

This is enforced structurally in the 11-step policy pipeline:

1. Step 3 (TOOL PERMISSION) passes — the agent has `is_allowed=true` for the tool
2. Step 6 (RISK LEVEL) runs — looks up the tool's `risk_level` and the organization's RISK policy
3. The default RISK policy maps `CRITICAL → DENY`
4. The engine returns DENY before reaching steps 7–11

This means that even an ADMIN cannot make a CRITICAL tool executable by granting permissions. The only way to allow a CRITICAL tool would be to modify the RISK policy rules to map `CRITICAL → ALLOW`, which is an auditable policy change — not a permission-level override.

This design is verified in the Phase 19 demo (`docs/demo-recording/phase19-complete.md`, Steps 5A/5B), where `delete_database` is denied both without and with explicit permission grants.

---

## Rate Limiting & Budget Guard

### Fail-Closed Policy

Both the rate limiter and budget guard follow a **fail-closed** policy: if Redis is unreachable, requests are denied by default rather than allowed.

```python
# From budget_guard.py and rate_limiter.py:
# If Redis raises ConnectionError, the checker returns (False, "Redis unavailable, fail-closed")
```

### Rate Limiting

- **Algorithm:** Sliding-window via Redis Sorted Sets (ZSET)
- **Window:** 60 seconds
- **Dimensions:** Per-agent requests/minute, per-agent tokens/minute
- **Defaults:** 60 requests/minute, 100,000 tokens/minute
- **Configurable:** Via the `budgets` table fields `max_requests_per_minute`, `max_tokens_per_minute`

### Budget Enforcement

- **Session cost cap** — `max_budget_per_session` (Redis counter, 1-hour TTL)
- **Daily cost cap** — `max_budget_per_day` (Redis counter, keyed by UTC date)
- **Session token cap** — `max_tokens_per_session` (500,000 default)
- **Source of truth for limits:** PostgreSQL `budgets` table
- **Source of truth for running totals:** Redis counters

**Known limitation:** If Redis data is lost (e.g., restart without persistence), running totals reset to zero. The budget *limits* are safe in PostgreSQL, but the counters are volatile.

---

## Input Validation

### Prohibited Parameter Patterns (Step 10)

The policy engine scans all parameter values against a regex denylist for destructive patterns:

```python
DEFAULT_PROHIBITED_PATTERNS = [
    r"(?i)\bdrop\s+table\b",
    r"(?i)\bdelete\s+from\b",
    r"(?i)\btruncate\s+table\b",
    r"(?i)\balter\s+table\b",
    r"(?i)\brm\s+-rf\b",
    r"(?i)\bmkfs\b",
    r"(?i)\bformat\s+[a-z]:",
    r"(?i)\bchmod\s+-R\s+777\b",
    r"(?i)\bshutdown\b",
    r"(?i)\bsudo\s+rm\b",
    r">\s*/dev/sd[a-z]",
]
```

These patterns are the defaults. Organizations can customize them via a `PARAM_DENYLIST` policy in the `policies` table.

The scanner recursively inspects nested dicts and lists — not just top-level parameter values.

### Suspicious Request Heuristics (Step 11)

| Threshold | Default | Effect |
|-----------|---------|--------|
| Payload size | 64 KB | DENY |
| Parameter key count | 50 | DENY |
| Estimated tokens | 100,000 | DENY |
| Estimated cost | $10,000 | DENY |

---

## CORS Configuration

CORS is configured via the `CORS_ORIGINS` environment variable:

```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**For production:** `CORS_ORIGINS` must be set to the exact frontend domain (e.g., `https://dashboard.example.com`). The default `http://localhost:3000` is suitable for local development only.

---

## Mock Tool Safety

All tool executions in AgentGuard are safe mocks:

| Tool | Risk | Has Handler | Behavior |
|------|------|------------|----------|
| `read_customer` | LOW | Yes | Returns fake customer profile |
| `send_email` | MEDIUM | Yes | Returns fake sent confirmation |
| `create_ticket` | MEDIUM | Yes | Returns fake ticket ID |
| `process_refund` | HIGH | Yes | Returns fake refund confirmation (only after HITL approval) |
| `delete_database` | CRITICAL | **No** | No handler exists. If policy ever returns ALLOW, that's a bug. |

> **Invariant:** `delete_database` has no registered handler in `mock_tools.py`. Even if the policy engine were somehow bypassed to return ALLOW, the gateway would record `execution_status: "skipped_no_handler"` and no destructive action would occur.

---

## Known Security Limitations

1. **No refresh tokens** — tokens expire and require full re-login (email/password users must re-authenticate; Google users must re-run the OAuth flow)
2. **No MFA** — single-factor authentication only (password or Google account)
3. **No password reset** — no forgot-password or email verification flow
4. **No HTTPS enforcement** — TLS termination is expected to be handled by the reverse proxy or hosting platform, not by the application
5. **Default JWT secret** — the fallback `JWT_SECRET` in `config.py` is a hardcoded development value. Production deployments **must** set the `JWT_SECRET` environment variable to a unique, cryptographically random string.
6. **API key plaintext in response** — the raw API key is returned in the `POST /auth/api-keys` response body. It's shown once and never stored, but it travels in the HTTP response — HTTPS is essential.
7. **No IP allowlisting** — API keys are not bound to source IP addresses
8. **Redis counter volatility** — rate limit and budget counters are in Redis memory. If Redis restarts without persistence, they reset.
9. **OAuth consent screen testing restriction** — if the Google OAuth consent screen is in "Testing" mode (not Published), only explicitly added test users can complete the Google sign-in flow. Public users will see a 403 error from Google.
10. **Exchange code in-process storage** — the OAuth exchange codes are stored in process memory, not Redis or a database. In a multi-process deployment (multiple Uvicorn workers), a code stored by one worker process cannot be consumed by a different process. Single-worker or single-instance deployments are not affected.
