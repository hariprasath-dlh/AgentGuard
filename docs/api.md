# API Reference

This document describes every REST API endpoint exposed by the AgentGuard Core Engine. All endpoints are prefixed with `/api/v1`.

The canonical machine-readable specification is available at [`docs/openapi.json`](openapi.json), served live by the running backend at `GET /openapi.json`.

---

## Authentication

The API uses three authentication mechanisms:

1. **JWT Bearer Token** — for dashboard users (humans). Obtained via `POST /api/v1/auth/login` (email/password) or via the Google OAuth 2.0 flow ending with `POST /api/v1/auth/google/exchange`. Passed as `Authorization: Bearer <token>`.
2. **API Key** — for agents (autonomous systems). Created via `POST /api/v1/auth/api-keys`. Passed as `X-API-Key: ag_live_...` header or as a Bearer token starting with `ag_`.
3. **Google OAuth 2.0** — for human users who sign in with their Google account. Flow: `GET /auth/google/login` → Google → `GET /auth/google/callback` → `POST /auth/google/exchange` → JWT token.

---

## RBAC Roles

Every user has exactly one role within their organization:

| Role | Description |
|------|------------|
| `ADMIN` | Full access to all endpoints |
| `SECURITY` | Can manage agents, tools, policies, budgets, permissions |
| `AUDITOR` | Read-only access + audit vault verification |
| `MANAGER` | Can view most resources + approve/deny HITL requests |
| `DEVELOPER` | Can create agents and tools, read most resources |

---

## Endpoints by Resource

### Auth

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | Public | Register a new user (email/password). Creates or joins an organization. |
| `POST` | `/auth/login` | Public | Authenticate with email/password and receive a JWT access token. |
| `GET` | `/auth/google/login` | Public | Initiate Google OAuth 2.0 Authorization Code flow. Redirects to Google. |
| `GET` | `/auth/google/callback` | Public | Google OAuth redirect target. Exchanges code, provisions user, redirects to frontend with a short-lived exchange code. |
| `POST` | `/auth/google/exchange` | Public | Exchange a short-lived one-time code (from Google callback redirect) for the actual JWT access token. |
| `POST` | `/auth/refresh` | Public | Refresh a JWT access token using a refresh token. |
| `GET` | `/auth/me` | Any authenticated | Return current user profile (includes organization_name, organization_slug). |
| `POST` | `/auth/api-keys` | Any authenticated | Create a new API key. Raw key shown **once**. |
| `GET` | `/auth/api-keys` | Any authenticated | List all active API keys for the caller's organization. |
| `DELETE` | `/auth/api-keys/{key_id}` | Any authenticated | Revoke an API key. |

#### POST /auth/register

```json
// Request
{
  "email": "admin@example.com",
  "password": "SecureP@ss123",
  "full_name": "Jane Admin",
  "organization_name": "Acme Corp",
  "organization_slug": "acme-corp",
  "role": "ADMIN"
}

// Response (201)
{
  "id": "uuid",
  "organization_id": "uuid",
  "organization_name": "Acme Corp",
  "organization_slug": "acme-corp",
  "role": "ADMIN",
  "email": "admin@example.com",
  "full_name": "Jane Admin",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

#### POST /auth/login

```json
// Request
{
  "email": "admin@example.com",
  "password": "SecureP@ss123",
  "organization_slug": "acme-corp"  // optional if email is unique across orgs
}

// Response (200)
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

> **Note:** No refresh token is issued for the email/password flow. When the access token expires (default: 30 minutes), the user must re-authenticate.

---

#### GET /auth/google/login

Initiates the Google OAuth 2.0 Authorization Code flow. Generates a cryptographically signed CSRF `state` token (JWT, 10-minute TTL) and redirects to Google's authorization endpoint.

**Query parameters:**
- `redirect_target` (optional, string) — the frontend URL to redirect to after authentication. Defaults to `FRONTEND_URL/login`.

**Response:** `307 Temporary Redirect` to Google OAuth consent page.

---

#### GET /auth/google/callback

Google redirects here after the user grants consent. This endpoint:
1. Validates the `state` JWT (CSRF protection — invalid or expired state → redirect to `/login?error=invalid_or_expired_state`)
2. Exchanges the `code` for tokens via Google's token endpoint
3. Verifies the Google ID token signature and audience
4. Resolves or auto-provisions the user account (globally-unique email lookup)
5. Issues a short-lived (60-second), single-use opaque exchange code
6. Redirects to `redirect_target?code=<exchange_code>`

**Query parameters (from Google):** `code`, `state`, `scope`, `authuser`, `prompt`

**Response:** `307 Temporary Redirect` to the frontend with `?code=<exchange_code>`.

> The JWT token is **never** placed in a URL. The exchange code is the only thing in the redirect URL, and it is single-use and expires in 60 seconds.

---

#### POST /auth/google/exchange

Exchanges the short-lived opaque code (received in the frontend from the callback redirect) for the actual JWT access token. This is the final step of the OAuth flow and is called by the frontend JavaScript, not via redirect.

```json
// Request
{
  "code": "<opaque-exchange-code>"
}

// Response (200)
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}

// Response (400) — code expired, already used, or invalid
{
  "detail": "Invalid, expired, or already used exchange code"
}
```

---

#### POST /auth/api-keys

```json
// Request
{
  "name": "FinanceAgent Key",
  "agent_id": "uuid",          // optional: bind to specific agent
  "expires_at": "2027-01-01T00:00:00Z"  // optional
}

// Response (201)
{
  "id": "uuid",
  "name": "FinanceAgent Key",
  "key_prefix": "ag_live",
  "api_key": "ag_live_abc123def456...",   // SHOWN ONCE — never stored in plaintext
  "agent_id": "uuid",
  "organization_id": "uuid",
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

### Agents

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `POST` | `/agents` | ADMIN, SECURITY, DEVELOPER | Create agent (auto-provisions budget + API key) |
| `GET` | `/agents` | All roles | List agents in caller's organization |
| `GET` | `/agents/{id}` | All roles | Get single agent |
| `PATCH` | `/agents/{id}` | ADMIN, SECURITY | Update agent (name, description, status) |
| `DELETE` | `/agents/{id}` | ADMIN, SECURITY | Soft delete (status → DELETED) |

#### POST /agents

```json
// Request
{
  "name": "FinanceAgent",
  "description": "Handles customer refunds and billing"
}

// Response (201) — includes one-time API key
{
  "id": "uuid",
  "name": "FinanceAgent",
  "description": "Handles customer refunds and billing",
  "status": "ACTIVE",
  "organization_id": "uuid",
  "api_key": "ag_live_...",        // ONE-TIME REVEAL
  "api_key_prefix": "ag_live",
  "budget": { ... },
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

### Tools

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `POST` | `/tools` | ADMIN, SECURITY, DEVELOPER | Create tool with risk level |
| `GET` | `/tools` | All roles | List tools |
| `GET` | `/tools/{id}` | All roles | Get single tool |
| `PATCH` | `/tools/{id}` | ADMIN, SECURITY | Update tool (name, risk_level, is_active) |

No DELETE endpoint — tools are retired by setting `is_active=false` to preserve referential integrity with historical `tool_requests`.

#### POST /tools

```json
// Request
{
  "name": "process_refund",
  "description": "Process customer refund",
  "risk_level": "HIGH"
}

// Response (201)
{
  "id": "uuid",
  "name": "process_refund",
  "description": "Process customer refund",
  "risk_level": "HIGH",
  "is_active": true,
  "organization_id": "uuid",
  "created_at": "2026-01-01T00:00:00Z"
}
```

Risk levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

---

### Permissions

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `POST` | `/permissions` | ADMIN, SECURITY | Grant permission (upsert) |
| `DELETE` | `/permissions/{id}` | ADMIN, SECURITY | Revoke permission |
| `GET` | `/permissions` | All roles | List permissions |

#### POST /permissions

```json
// Request
{
  "agent_id": "uuid",
  "tool_id": "uuid",
  "is_allowed": true
}
```

---

### Policies

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `POST` | `/policies` | ADMIN, SECURITY | Create policy |
| `GET` | `/policies` | ADMIN, SECURITY, AUDITOR, MANAGER | List policies |
| `GET` | `/policies/{id}` | ADMIN, SECURITY, AUDITOR, MANAGER | Get single policy |
| `PATCH` | `/policies/{id}` | ADMIN, SECURITY | Update policy |
| `DELETE` | `/policies/{id}` | ADMIN, SECURITY | Soft delete (is_active → false) |

Policy types and their `rules` JSON structure:

```json
// RISK policy
{
  "name": "Default Risk Policy",
  "policy_type": "RISK",
  "rules": {
    "risk_rules": {
      "LOW": "ALLOW",
      "MEDIUM": "ALLOW",
      "HIGH": "HITL",
      "CRITICAL": "DENY"
    }
  }
}

// PARAM_DENYLIST policy
{
  "name": "SQL Injection Guard",
  "policy_type": "PARAM_DENYLIST",
  "rules": {
    "patterns": [
      "(?i)\\bdrop\\s+table\\b",
      "(?i)\\bdelete\\s+from\\b"
    ]
  }
}
```

---

### Budgets

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `GET` | `/budgets` | ADMIN, SECURITY, AUDITOR, MANAGER | List budgets |
| `PATCH` | `/budgets/{id}` | ADMIN, SECURITY | Update budget caps |

No POST — budgets are auto-provisioned when agents are created.

#### PATCH /budgets/{id}

```json
// Request
{
  "max_budget_per_session": 100.0,
  "max_budget_per_day": 500.0,
  "max_tokens_per_session": 500000,
  "max_requests_per_minute": 60,
  "max_tokens_per_minute": 100000
}
```

---

### Guard (The Core Endpoint)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/guard/check` | API Key (X-API-Key) | Evaluate a proposed tool call |

This is the single, unavoidable chokepoint between an agent and its tools.

#### POST /guard/check

```json
// Request
{
  "agent_id": "uuid",
  "tool_name": "read_customer",
  "action": "execute",
  "parameters": {
    "customer_id": "CUST-9921"
  },
  "estimated_tokens": 500,
  "estimated_cost": 0.05,
  "metadata": {}
}

// Response (200) — ALLOW
{
  "decision": "ALLOW",
  "request_id": "uuid",
  "reason": "All policy checks passed."
}

// Response (200) — DENY
{
  "decision": "DENY",
  "request_id": "uuid",
  "reason": "Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy."
}

// Response (200) — PENDING
{
  "decision": "PENDING",
  "request_id": "uuid",
  "reason": "Action on tool 'process_refund' requires human approval (HITL)."
}
```

---

### HITL (Human-in-the-Loop)

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `GET` | `/hitl` | ADMIN, MANAGER | List HITL requests (with lazy expiration) |
| `GET` | `/hitl/{id}` | ADMIN, MANAGER | Get single HITL request |
| `POST` | `/hitl/{id}/approve` | ADMIN, MANAGER | Approve and resume tool execution |
| `POST` | `/hitl/{id}/deny` | ADMIN, MANAGER | Deny — no tool execution |

#### POST /hitl/{id}/approve

```json
// Request (optional body)
{
  "review_notes": "Approved VIP refund per customer agreement"
}

// Response (200)
{
  "id": "uuid",
  "status": "APPROVED",
  "reviewer_id": "uuid",
  "review_notes": "Approved VIP refund per customer agreement",
  "tool_name": "process_refund",
  "input_payload": { ... },
  "output_payload": { ... },  // mock handler result
  "reviewed_at": "2026-01-01T00:05:00Z",
  ...
}
```

---

### Audit Vault

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `GET` | `/audit` | ADMIN, AUDITOR | List audit log records |
| `GET` | `/audit/{id}` | ADMIN, AUDITOR | Get single audit record |
| `POST` | `/audit/verify` | ADMIN, AUDITOR | Verify hash chain integrity |

#### POST /audit/verify

```json
// Response (200) — valid chain
{
  "status": "VALID",
  "total_records": 20,
  "message": "Tamper-evident cryptographic hash chain verified successfully.",
  "broken_record_id": null,
  "broken_sequence_number": null,
  "error_type": null,
  "duration_ms": 12.5
}

// Response (200) — tampered chain
{
  "status": "INVALID",
  "total_records": 20,
  "message": "Tampering detected at sequence number 7: data modification detected.",
  "broken_record_id": "uuid",
  "broken_sequence_number": 7,
  "error_type": "HASH_MISMATCH",
  "details": "Recomputed hash '...' does not match stored current_hash '...'",
  "early_exit_note": "Verification stopped at first break; records after this point were not checked.",
  "duration_ms": 5.2
}
```

---

### Dashboard

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `GET` | `/dashboard/stats` | All authenticated | Aggregate stats (agents, tools, requests, spend) |
| `GET` | `/dashboard/activity` | All authenticated | Recent activity feed |

---

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Liveness probe |
| `GET` | `/ready` | None | Readiness probe |

Both return `{"status": "healthy"}` / `{"status": "ready"}`.

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (validation failure, invalid state transition) |
| 401 | Missing or invalid authentication credentials |
| 403 | Authenticated but insufficient role permissions |
| 404 | Resource not found in caller's organization |
| 409 | Conflict (e.g., duplicate email registration) |
| 422 | Validation error (Pydantic schema violation) |
| 500 | Internal server error (audit commit failure, etc.) |

---

## Organization Isolation

Every endpoint that reads or writes data filters by the caller's `organization_id`, extracted from the JWT token or API key. There is no endpoint that allows cross-organization data access. This is enforced at the repository layer, not just the API layer.
