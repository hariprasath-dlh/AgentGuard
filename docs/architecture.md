# Architecture

This document describes AgentGuard's system architecture as it is actually implemented in the codebase today.

---

## Three-Component Structure

AgentGuard is a hybrid B2B SaaS product made of three components:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Component C                                  │
│                   Control Plane (Dashboard)                         │
│            TanStack Start / React 19 / TypeScript                   │
│                                                                     │
│   Dashboard │ Agents │ Tools │ Policies │ Budgets │ Approvals       │
│   Audit Vault │ Settings                                            │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ HTTP (JWT auth)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Component A                                  │
│                Core Engine (FastAPI Backend)                         │
│                                                                     │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│   │ Auth / RBAC  │  │ Policy Engine│  │ Guard Gateway            │ │
│   │ JWT + API Key│  │ 11-step      │  │ POST /guard/check        │ │
│   └──────────────┘  │ pipeline     │  │ (the single chokepoint)  │ │
│                     └──────────────┘  └──────────────────────────┘ │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│   │ Rate Limiter │  │ Budget Guard │  │ Audit Vault              │ │
│   │ Redis ZSET   │  │ Redis + PG   │  │ SHA-256 Hash Chain       │ │
│   └──────────────┘  └──────────────┘  └──────────────────────────┘ │
│   ┌──────────────┐  ┌──────────────┐                               │
│   │ HITL Engine  │  │ Mock Tools   │                               │
│   │ PENDING flow │  │ Safe handlers│                               │
│   └──────────────┘  └──────────────┘                               │
└───────────────────┬─────────────────────┬───────────────────────────┘
                    │                     │
                    ▼                     ▼
            ┌──────────────┐      ┌──────────────┐
            │ PostgreSQL   │      │ Redis 7      │
            │ 12 tables    │      │ Rate limits  │
            │ Audit chain  │      │ Budget totals│
            └──────────────┘      └──────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        Component B                                  │
│                    Python SDK (agentguard-sdk)                       │
│                                                                     │
│   AgentGuard(api_key=...) → client.guard(tool=..., params=...)     │
│   → HTTP POST /guard/check → raises Denied/Pending or returns OK   │
│                                                                     │
│   Installed via: pip install -e ./sdk                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Request Flow: End-to-End Decision Pipeline

When an agent proposes a tool call, this is the exact sequence:

```mermaid
sequenceDiagram
    participant Agent as AI Agent (via SDK)
    participant Gateway as Guard Gateway<br/>POST /guard/check
    participant Engine as Policy Engine<br/>(11 steps)
    participant Redis as Redis<br/>(Rate Limits + Budgets)
    participant PG as PostgreSQL<br/>(Models + Audit)
    participant HITL as HITL Queue
    participant Tool as Mock Tool Handler

    Agent->>Gateway: POST /guard/check<br/>{tool_name, agent_id, parameters, ...}
    Gateway->>Gateway: Authenticate via X-API-Key header
    Gateway->>Engine: evaluate(input_data, caller)

    Note over Engine: Step 1: AUTH — verify caller identity
    Note over Engine: Step 2: AGENT STATUS — check ACTIVE
    Engine->>PG: Query agent by ID + org
    Note over Engine: Step 3: TOOL PERMISSION — check grant
    Engine->>PG: Query agent_tool_permissions
    Note over Engine: Step 4: TOOL ENABLED — is_active=true
    Note over Engine: Step 5: ACTION ALLOWED — non-empty action
    Note over Engine: Step 6: RISK LEVEL — policy lookup
    Engine->>PG: Query policies (type=RISK)

    alt CRITICAL risk
        Engine-->>Gateway: DENY (risk policy)
    end

    Note over Engine: Step 7: BUDGET
    Engine->>Redis: Check session + daily cost
    Note over Engine: Step 8: RATE LIMIT
    Engine->>Redis: Check sliding window ZSET
    Note over Engine: Step 9: HITL — flag if HIGH risk
    Note over Engine: Step 10: PROHIBITED PARAMETERS — regex scan
    Note over Engine: Step 11: SUSPICIOUS REQUEST — size/cost heuristics

    Engine-->>Gateway: DecisionOutput {ALLOW|DENY|PENDING}

    Gateway->>PG: record_audit_log() — SHA-256 hash chain
    Gateway->>PG: Create ToolRequest row
    alt PENDING decision
        Gateway->>PG: Create HITLRequest (expires in 24h)
    end
    Gateway->>PG: COMMIT (hard gate)

    alt ALLOW + handler exists
        Gateway->>Tool: Execute mock handler
        Tool-->>Gateway: Handler result
        Gateway->>PG: Update output_payload
    end

    Gateway-->>Agent: GuardResponse {decision, request_id, reason}
```

### Key Invariants

1. **Commit-before-execute:** The audit log and decision are committed to PostgreSQL *before* any mock tool handler runs. If the commit fails, the handler never executes.
2. **Server-generated request_id:** The gateway generates a UUID for each request. Client-supplied IDs are never trusted.
3. **Handler errors don't hide ALLOW:** If a mock handler throws, the ALLOW decision still stands — the error is recorded in `output_payload`.
4. **DENY > PENDING > ALLOW:** Even if HITL flags PENDING at step 9, steps 10–11 can still escalate to DENY.

---

## Data Model

The database has 12 tables. Here is their structure and relationships:

```mermaid
erDiagram
    organizations ||--o{ users : "has many"
    organizations ||--o{ roles : "has many"
    organizations ||--o{ agents : "has many"
    organizations ||--o{ tools : "has many"
    organizations ||--o{ policies : "has many"
    organizations ||--o{ budgets : "has many"
    organizations ||--o{ audit_logs : "has chain"
    organizations ||--o{ hitl_requests : "has many"

    users ||--o{ api_keys : "creates"
    users }o--|| roles : "has role"

    agents ||--o{ agent_tool_permissions : "granted"
    agents ||--o{ budgets : "has budget"
    agents ||--o{ api_keys : "authenticated by"

    tools ||--o{ agent_tool_permissions : "permitted"
    tools ||--o{ tool_requests : "requested"

    tool_requests ||--o| hitl_requests : "may trigger"
    tool_requests }o--|| audit_logs : "links to"

    organizations {
        uuid id PK
        string name
        string slug UK
        timestamp created_at
    }

    roles {
        uuid id PK
        uuid organization_id FK
        string name
    }

    users {
        uuid id PK
        uuid organization_id FK
        uuid role_id FK
        string email
        string hashed_password
        string full_name
        boolean is_active
        timestamp created_at
    }

    agents {
        uuid id PK
        uuid organization_id FK
        string name
        string description
        string status
        timestamp created_at
    }

    tools {
        uuid id PK
        uuid organization_id FK
        string name UK
        string description
        string risk_level
        boolean is_active
        timestamp created_at
    }

    agent_tool_permissions {
        uuid id PK
        uuid agent_id FK
        uuid tool_id FK
        boolean is_allowed
        uuid organization_id FK
    }

    policies {
        uuid id PK
        uuid organization_id FK
        string name
        string policy_type
        json rules
        boolean is_active
        timestamp created_at
    }

    budgets {
        uuid id PK
        uuid organization_id FK
        uuid agent_id FK
        float max_budget_per_session
        float max_budget_per_day
        int max_tokens_per_session
        int max_requests_per_minute
        int max_tokens_per_minute
        timestamp created_at
    }

    api_keys {
        uuid id PK
        uuid organization_id FK
        uuid agent_id FK
        uuid user_id FK
        string name
        string key_prefix
        string key_hash
        boolean is_active
        timestamp expires_at
        timestamp created_at
    }

    tool_requests {
        uuid id PK
        uuid organization_id FK
        uuid agent_id FK
        uuid tool_id FK
        uuid audit_log_id FK
        string decision
        string reason
        json input_payload
        json output_payload
        float latency_ms
        timestamp created_at
    }

    hitl_requests {
        uuid id PK
        uuid organization_id FK
        uuid tool_request_id FK
        string status
        uuid reviewer_id FK
        string review_notes
        timestamp expires_at
        timestamp reviewed_at
        timestamp created_at
        timestamp updated_at
    }

    audit_logs {
        uuid id PK
        uuid organization_id FK
        uuid agent_id FK
        uuid tool_id FK
        string event_type
        string decision
        json payload
        string previous_hash
        string current_hash
        bigint sequence_number
        timestamp created_at
    }
```

### Table Roles

| Table | Purpose |
|-------|---------|
| `organizations` | Multi-tenant isolation boundary. Every other table references this. |
| `roles` | Per-org role definitions: ADMIN, SECURITY, AUDITOR, MANAGER, DEVELOPER |
| `users` | Human users of the Control Plane. Authenticated via JWT. |
| `agents` | Registered AI agents. Authenticated via API keys. |
| `tools` | Registered tools with risk levels (LOW, MEDIUM, HIGH, CRITICAL). |
| `agent_tool_permissions` | Explicit grants: which agents can use which tools. Unique on (agent_id, tool_id). |
| `policies` | Policy rules: RISK mappings, PARAM_DENYLIST patterns. JSON rules column. |
| `budgets` | Per-agent cost and rate limits. Auto-provisioned at agent creation. |
| `api_keys` | SHA-256 hashed API keys. Plaintext shown once at creation, never stored. |
| `tool_requests` | Records of each guard evaluation with input/output payloads. |
| `hitl_requests` | PENDING → APPROVED/DENIED/EXPIRED lifecycle for HIGH-risk decisions. |
| `audit_logs` | SHA-256 hash-chained, tamper-evident decision records. Per-organization chains. |

---

## The 11-Step Policy Pipeline (Detail)

The policy engine is implemented in `backend/app/services/policy_engine.py` as the `PolicyEngine` class. It is a purely deterministic evaluator — no LLM calls, no prompt evaluation.

> **Note:** `project.md` describes a "9-step pipeline." The actual implementation has 11 steps. Steps 4 (TOOL ENABLED) and 5 (ACTION ALLOWED) were added during implementation to handle edge cases the original 9-step spec didn't cover. Steps 10 (PROHIBITED PARAMETERS) and 11 (SUSPICIOUS REQUEST) were added as additional safety guardrails in Phase 5.

| Step | Name | Fails → | Data Source |
|------|------|---------|------------|
| 1 | AUTH | DENY | CallerIdentity (from API key resolution) |
| 2 | AGENT STATUS | DENY | `agents` table (status = ACTIVE) |
| 3 | TOOL PERMISSION | DENY | `agent_tool_permissions` table |
| 4 | TOOL ENABLED | DENY | `tools` table (is_active flag) |
| 5 | ACTION ALLOWED | DENY | Request payload (non-empty action) |
| 6 | RISK LEVEL | DENY or flag HITL | `policies` table (type=RISK) + `tools.risk_level` |
| 7 | BUDGET | DENY | Redis counters + `budgets` table |
| 8 | RATE LIMIT | DENY | Redis ZSET sliding windows |
| 9 | HITL | flag PENDING | If HIGH risk was flagged at step 6 |
| 10 | PROHIBITED PARAMS | DENY | `policies` table (type=PARAM_DENYLIST) + defaults |
| 11 | SUSPICIOUS REQUEST | DENY | Request payload size/token/cost thresholds |

The engine short-circuits on the first DENY at steps 1–8, but steps 9–11 always run together because a PENDING decision must still be checked for prohibited parameters (DENY overrides PENDING).

---

## Service Layer

| Service | File | Responsibility |
|---------|------|---------------|
| `PolicyEngine` | `services/policy_engine.py` | 11-step deterministic pipeline orchestrator |
| `record_audit_log` | `services/audit_vault.py` | SHA-256 hash chain append with org-scoped row locking |
| `verify_organization_chain` | `services/audit_vault.py` | Sequential chain verification with early-exit on break |
| `RedisBudgetChecker` | `services/budget_guard.py` | Session/daily cost caps via Redis + PG |
| `RedisRateLimitChecker` | `services/rate_limiter.py` | Sliding-window ZSET rate limiting |
| `get_handler` | `services/mock_tools.py` | Safe mock tool handler registry |
| `create_policy_engine` | `services/factory.py` | Factory that wires Redis-backed checkers into the engine |

---

## Frontend Architecture

The Control Plane is a **TanStack Start** (Vite-based) application with file-based routing:

| Screen | Route | Purpose |
|--------|-------|---------|
| Dashboard | `/dashboard` | Live stats, budget utilization, activity feed |
| Agents | `/agents` | Register, edit, deactivate agents |
| Tools & Permissions | `/tools` | Register tools, assign risk levels, manage permissions |
| Policies | `/policies` | Create/edit risk and parameter denylist policies |
| Budgets | `/budgets` | View/edit per-agent session and daily caps |
| Approvals | `/approvals` | HITL queue — approve or deny pending requests |
| Audit Vault | `/audit` | Hash-chain viewer with "Verify Chain" button |
| Settings | `/settings` | Organization and user profile |

> **Deviation from `project.md`:** The spec calls for "Next.js." The actual implementation uses TanStack Start (a Vite-based React framework) because the frontend was built via Lovable AI, which generates TanStack Start projects. The functionality is equivalent — it's still a React/TypeScript SPA that talks to the backend via the versioned REST API.
