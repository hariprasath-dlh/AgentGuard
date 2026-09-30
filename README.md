# AgentGuard

**Framework-Agnostic Runtime Governance Layer for Autonomous AI Agents**

AgentGuard is a pre-dispatch security and governance control plane that sits between an AI agent and the tools/APIs it calls. It intercepts every proposed tool call *before* execution, evaluates it against RBAC permissions, budget/rate limits, and risk policy, and only allows the call through if it passes. High-risk actions pause for asynchronous human approval. Every decision is written to a cryptographically hash-chained, tamper-evident audit log.

> **The agent proposes. AgentGuard decides. The tool executes only after AgentGuard allows it.**

---

## The Problem

Enterprises adopting autonomous AI agents face five concrete problems that existing tools don't solve:

1. **Runaway costs** — agents can rack up catastrophic API bills with no runtime rate-limiter.
2. **Unchecked tool access** — agents with direct tool access can execute destructive commands or leak data with no runtime RBAC.
3. **No runtime governance** — orchestration frameworks like LangChain/CrewAI handle build-time logic but have no runtime governance layer.
4. **Mutable audit logs** — standard database logs are mutable and fail regulatory evidentiary requirements (e.g. EU AI Act Article 12).
5. **No async human oversight** — there is no native way to pause an agent for human approval on high-risk actions and resume it later.

## The Solution

AgentGuard solves all five with one architecture:

- A **pre-dispatch interception proxy** (`POST /guard/check`) — the single chokepoint every tool call passes through
- **Redis-backed sliding-window rate limits** and **hard budget caps** per agent
- **Strict RBAC** enforced per tool call, with organization isolation
- A **SHA-256 hash-chain audit vault** — tamper-evident (not tamper-proof), cryptographically verifiable
- A **Human-in-the-Loop (HITL) queue** for async approval of HIGH-risk actions
- A **web Control Plane** for human administrators to manage agents, tools, policies, budgets, and approvals

The system is **framework-agnostic** — it speaks plain JSON over HTTP, so it works with any agent framework.

---

## Architecture

AgentGuard consists of three components:

```
┌────────────────────────────────┐       ┌──────────────────────────┐       ┌────────────────────┐
│  Component B                   │       │  Component A              │       │  Component C        │
│  Python SDK                    │──────▶│  Core Engine (FastAPI)    │◀──────│  Control Plane      │
│  agentguard-governance-sdk     │ HTTP  │  Policy Engine + Audit    │ HTTP  │  (TanStack/React)   │
│  pip install                   │       │  PostgreSQL + Redis       │       │  Web Dashboard      │
└────────────────────────────────┘       └──────────────────────────┘       └────────────────────┘
```

**Component A — Core Engine (Backend API):** FastAPI microservice. The "bouncer" that intercepts JSON tool-call payloads, evaluates them through an 11-step deterministic policy pipeline, and returns ALLOW / DENY / PENDING decisions. This is the only component that talks to PostgreSQL and Redis directly.

**Component B — Python SDK:** Lightweight `agentguard-governance-sdk` package (`pip install agentguard-governance-sdk`). Provides a `client.guard(...)` method that routes tool calls through the Core Engine. The SDK never contains policy logic — it only calls the API and interprets the response.

**Component C — Control Plane (Web Dashboard):** TanStack Start / React / TypeScript web application. Shows live activity feeds, HITL approval queue, agent/tool/policy/budget management, and an Audit Vault viewer with one-click chain verification.

### The 11-Step Policy Decision Pipeline

Every tool call is evaluated through this deterministic pipeline in strict order:

1. **AUTH** — Verify caller identity (API key or JWT)
2. **AGENT STATUS** — Agent exists and is ACTIVE (not SUSPENDED/DELETED)
3. **TOOL PERMISSION** — Agent has explicit `agent_tool_permissions` grant
4. **TOOL ENABLED** — Tool's `is_active` flag is true
5. **ACTION ALLOWED** — Requested action string is non-empty
6. **RISK LEVEL** — Data-driven policy lookup: LOW/MEDIUM → ALLOW, HIGH → HITL, CRITICAL → DENY
7. **BUDGET** — Session and daily cost caps (Redis-backed)
8. **RATE LIMIT** — Sliding-window requests/tokens per minute (Redis ZSET)
9. **HITL** — If HIGH risk flagged, mark as PENDING for human review
10. **PROHIBITED PARAMETERS** — Regex denylist for SQL injection, shell commands, etc.
11. **SUSPICIOUS REQUEST** — Payload size, token count, and cost threshold heuristics

**Precedence:** DENY > PENDING > ALLOW. Even if HITL flags PENDING, checks 10–11 can still DENY a malicious payload before it reaches a human reviewer.

---

## Features

- **Pre-dispatch interception** — blocked requests never reach the tool
- **5-role RBAC** — ADMIN, SECURITY, AUDITOR, MANAGER, DEVELOPER with per-endpoint enforcement
- **Organization isolation** — every query is scoped to the caller's organization
- **Budget enforcement** — session and daily cost caps, session token limits
- **Sliding-window rate limiting** — per-agent requests/minute and tokens/minute via Redis ZSET
- **CRITICAL-risk override invariant** — CRITICAL tools are denied by policy even if explicitly permitted
- **Human-in-the-Loop** — HIGH-risk actions queue for async human approval with 24-hour expiration
- **SHA-256 hash-chain audit vault** — tamper-evident, cryptographically verifiable, per-organization chains
- **Structured JSON logging** — every guard decision logged with request_id, agent_id, organization_id, decision, latency_ms
- **Health/readiness probes** — `GET /health` and `GET /ready` endpoints

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | PostgreSQL 15 (production) / SQLite (local dev fallback) |
| Cache & Rate Limiting | Redis 7 (sorted sets for sliding windows) |
| Auth | JWT (PyJWT), bcrypt password hashing, Google OAuth 2.0, API key authentication |
| Audit | SHA-256 hash chaining with canonical JSON serialization |
| SDK | Python, httpx, Pydantic — `agentguard-governance-sdk` package |
| Frontend | TanStack Start, React 19, TypeScript, Tailwind CSS, Radix UI |
| E2E Testing | Playwright (Chromium, Firefox, Mobile Chromium), axe-core |
| Infrastructure | Docker Compose (local), free-tier managed services (production) |

---

## Getting Started

### Prerequisites

- **Python 3.11+** (for backend and SDK)
- **Node.js 18+** and **npm** (for frontend)
- **Docker** and **Docker Compose** (for PostgreSQL and Redis)
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/agentguard.git
cd agentguard
```

### 2. Start Infrastructure (PostgreSQL + Redis)

```bash
docker compose up -d postgres redis
```

This starts:
- PostgreSQL 15 on `localhost:5432` (user: `agentguard`, password: `agentguard_password`, db: `agentguard`)
- Redis 7 on `localhost:6379`

### 3. Set Up the Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file (or set environment variables):

```bash
cp ../.env.example .env
```

The `.env.example` contains:
```
DATABASE_URL=postgresql://agentguard:agentguard_password@localhost:5432/agentguard
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-here
API_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000
AGENTGUARD_ENV=development
```

> **Note:** For quick local development without Docker, the backend falls back to SQLite automatically if `DATABASE_URL` is not set. Some features (row-level locking for audit chain concurrency) require PostgreSQL.

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Verify:
```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

### 4. Seed Demo Data

The demo scripts set up a complete scenario with users, agents, tools, and policies:

```bash
cd ../demo
python run_demo_scenario.py
```

This creates:
- An organization (`agentguard-demo`) with ADMIN, MANAGER, AUDITOR, and DEVELOPER users
- A `FinanceAgent` with API key
- Tools: `read_customer` (LOW), `send_email` (MEDIUM), `process_refund` (HIGH), `delete_database` (CRITICAL)
- Policies and permissions

### 5. Set Up the Frontend

```bash
cd ../frontend
npm install
npm run dev
```

The Control Plane is now live at `http://localhost:3000`.

### 6. Install the SDK

```bash
pip install agentguard-governance-sdk
```

For local development from source:
```bash
cd ../sdk
pip install -e .
```

---

## SDK Quick Start

```python
from agentguard import AgentGuard, AgentGuardDenied, AgentGuardPending

client = AgentGuard(
    api_key="ag_live_...",  # from POST /api/v1/auth/api-keys
    base_url="http://localhost:8000/api/v1",
    agent_id="<agent-uuid>",
)

# LOW-risk tool — will be ALLOWED
result = client.guard(tool="read_customer", parameters={"customer_id": "CUST-9921"})
if result.allowed:
    print("Tool call permitted, execute it")

# HIGH-risk tool — will raise AgentGuardPending
try:
    client.guard(
        tool="process_refund",
        parameters={"customer_id": "CUST-9921", "amount": 75000.0},
        estimated_cost=75000.0,
    )
except AgentGuardPending as e:
    print(f"Paused for human review: {e.reason}")
    print(f"Track with request_id: {e.request_id}")

# CRITICAL-risk tool — will raise AgentGuardDenied
try:
    client.guard(tool="delete_database", parameters={"target": "production"})
except AgentGuardDenied as e:
    print(f"Blocked by policy: {e.reason}")
```

See [docs/sdk.md](docs/sdk.md) for the full API reference.

---

## Demo Scenario

The canonical demo is the **FinanceAgent refund flow**, which exercises all five governance guarantees in sequence:

1. `read_customer` (LOW risk) → **ALLOW**
2. `send_email` (MEDIUM risk) → **ALLOW**
3. `process_refund` (HIGH risk) → **PENDING** (agent pauses for human review)
4. Manager approves → tool executes, refund confirmed
5. `delete_database` (CRITICAL risk) → **DENY** (even with explicit permission grant)
6. Auditor runs `POST /audit/verify` → **CHAIN VALID** across all records

Full instructions: [docs/demo.md](docs/demo.md)

---

## Testing

The project includes:

- **Backend unit tests** — pytest, covering all 11 policy engine checks, audit vault hash computation, HITL lifecycle
- **Backend integration tests** — httpx TestClient against the live API
- **Frontend E2E tests** — Playwright across Chromium, Firefox, and Mobile Chromium (177 test executions from 59 unique test cases × 3 browser projects)
- **Accessibility** — axe-core WCAG 2.1 AA scans on all 10 screens

Run backend tests:
```bash
cd backend
pytest tests/ -v --cov=app
```

Run frontend E2E tests:
```bash
cd frontend
npx playwright test
```

---

## Security Model

- **JWT authentication** for dashboard users (email/password or Google OAuth 2.0 with signed `state` CSRF protection and 60-second single-use exchange codes; no refresh tokens)
- **Global email uniqueness** — `users.email` is globally unique across organizations, preventing duplicate account collision between OAuth and password flows
- **Audit integrity** — `hitl_requests.reviewer_id` foreign key enforces `ON DELETE RESTRICT` to preserve reviewer audit trails
- **API key authentication** for agents (SHA-256 hashed storage, plaintext shown exactly once at creation)
- **5-role RBAC** with per-endpoint enforcement via `require_role()` dependency injection
- **Organization isolation** — every database query is scoped by `organization_id`
- **CRITICAL-risk override** — structurally enforced in the policy engine; CRITICAL tools are denied at step 6 regardless of permission grants at step 3
- **Fail-closed rate limiting** — if Redis is unreachable, requests are denied by default
- **Parameter denylist** — regex patterns for SQL injection, shell commands, and destructive operations
- **CORS** — configurable via `CORS_ORIGINS` environment variable

See [docs/security.md](docs/security.md) for the full security model.

---

## Known Limitations

These are honest, documented limitations of the current implementation:

1. **No refresh tokens** — JWT access tokens expire and require full re-authentication. There is no silent token refresh.
2. **No password reset** — the system has no forgot-password or email verification flow.
3. **SQLite fallback limitations** — the `SELECT ... FOR UPDATE` row-level locking used for audit chain concurrency is a no-op in SQLite. Running with SQLite means concurrent requests to the same organization can produce race conditions in sequence number allocation. PostgreSQL is required for production correctness.
4. **Audit chain throughput tradeoff** — the per-organization row-level lock on the `organizations` table serializes all audit writes within a single organization. This guarantees gapless, monotonic sequence numbers but limits write throughput to one audit record at a time per organization. Different organizations process fully in parallel.
5. **No WebSocket/SSE real-time feeds** — the dashboard uses polling (5–15 second intervals) for live data, not push-based updates.
6. **Mock tool handlers only** — all tool executions are safe mocks that return plausible fake data. `delete_database` has no handler and will never execute.
7. **No multi-factor authentication** — single-factor JWT auth only.
8. **Rate limit and budget counters are in Redis** — if Redis data is lost (e.g., restart without persistence), counters reset. The PostgreSQL `budgets` table stores the *limits* but not the running totals.

---

## Documentation

| Document | Description |
|----------|------------|
| [USER_GUIDE.md](USER_GUIDE.md) | **Complete Beginner & User Guide** (Step-by-step setup, SDK integration, and FAQs) |
| [docs/architecture.md](docs/architecture.md) | System architecture, data model, and decision pipeline |
| [docs/api.md](docs/api.md) | REST API reference with RBAC restrictions |
| [docs/sdk.md](docs/sdk.md) | Python SDK reference and usage guide |
| [docs/security.md](docs/security.md) | Security model, RBAC matrix, and hardening results |
| [docs/audit.md](docs/audit.md) | Hash-chain audit vault design and verification |
| [docs/hitl.md](docs/hitl.md) | Human-in-the-Loop lifecycle and behavior |
| [docs/deployment.md](docs/deployment.md) | Production deployment runbook |
| [docs/demo.md](docs/demo.md) | FinanceAgent demo scenario instructions |

---

## Project Structure

```
agentguard/
├── backend/                  # Component A — Core Engine
│   ├── app/
│   │   ├── api/              # FastAPI route handlers
│   │   ├── core/             # Config, database connection
│   │   ├── models/           # SQLAlchemy ORM models (12 tables)
│   │   ├── repositories/     # Data access layer
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── security/         # JWT, API key, RBAC dependencies
│   │   ├── services/         # Policy engine, audit vault, rate limiter, budget guard
│   │   └── main.py           # FastAPI app entry point
│   ├── tests/                # pytest unit and integration tests
│   ├── Dockerfile
│   └── requirements.txt
├── sdk/                      # Component B — Python SDK
│   ├── agentguard/
│   │   ├── client.py         # AgentGuard client class
│   │   ├── guard.py          # HTTP evaluation with safe-retry logic
│   │   ├── models.py         # GuardRequest, GuardResult
│   │   └── exceptions.py     # 5 structured exception classes
│   └── pyproject.toml
├── frontend/                 # Component C — Control Plane
│   ├── src/
│   │   ├── routes/           # TanStack Router file-based routes
│   │   ├── components/       # UI components (Radix + custom)
│   │   └── lib/              # API client, utilities
│   └── e2e/                  # Playwright E2E test specs
├── demo/                     # Demo scripts and agents
├── docs/                     # Documentation
├── docker-compose.yml        # Local infrastructure
├── .env.example              # Environment variable template
└── project.md                # Project specification (source of truth)
```

---

## License

This project was developed as part of an academic research effort. See the repository for licensing details.
