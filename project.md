# PROJECT.md — AgentGuard

This file is the single source of truth for this project. Read it before writing or changing any code. If a request conflicts with this file, this file wins — flag the conflict instead of silently deviating.

## Title

AgentGuard — Framework-Agnostic Runtime Governance Layer for Autonomous AI Agents

## Description

AgentGuard is a pre-dispatch security and governance control plane that sits between an AI agent and the tools/APIs it calls. It intercepts every proposed tool call *before* execution, evaluates it against RBAC permissions, budget/rate limits, and risk policy, and only allows the call through if it passes. High-risk actions pause for asynchronous human approval. Every decision is written to a cryptographically hash-chained, tamper-evident audit log. AgentGuard does not compete with observability tools like LangSmith/Langfuse (which log what an agent *already did*); it governs what an agent is *about to do*.

## Your Role

You are the lead full-stack engineer implementing AgentGuard exactly as specified in this file. You are not the product designer — scope, architecture, and phase order are already decided and documented below. Your job is disciplined execution: implement the current phase completely and correctly, write tests before or alongside the implementation, and stop at phase boundaries rather than pulling forward work from later phases. If something in a request seems to require a new feature, a new dependency, or a change to the architecture below, say so explicitly and wait for confirmation before proceeding — do not quietly expand scope to be "more helpful."

## Context

Enterprises adopting autonomous AI agents face five concrete problems that existing tools don't solve: (1) runaway agents can rack up catastrophic API bills with no runtime rate-limiter, (2) agents with direct tool access can execute destructive commands or leak data with no runtime RBAC "bouncer," (3) orchestration frameworks like LangChain/CrewAI handle build-time logic but have no runtime governance layer, (4) audit logs in standard databases are mutable and fail regulatory evidentiary requirements (e.g. EU AI Act Article 12), and (5) there is no native way to pause an agent for async human approval on high-risk actions and resume it later without losing state.

AgentGuard solves all five with one architecture: a pre-dispatch interception proxy, Redis-backed sliding-window rate limits and hard budget caps, strict RBAC enforced per tool call, a SHA-256 hash-chain audit vault, and a Redis Streams-based async HITL queue. The whole system is framework-agnostic — it speaks plain JSON over HTTP, so it works with any agent framework, not just one.

The core identity of the product, unchanged across every phase: **the agent proposes, AgentGuard decides, the tool executes only after AgentGuard allows it.**

## Expected Output — Three Components

The finished project is a hybrid B2B SaaS product made of three components that must all work together. Do not treat any one of these as optional or as "the real product" with the others as afterthoughts — all three are required deliverables.

**Component A — The Core Engine (Backend API).** The invisible, high-performance FastAPI microservice. The "bouncer" that runs in the background: intercepts JSON tool-call payloads, evaluates policy/budget/risk/RBAC, and returns an ALLOW / DENY / PENDING decision in milliseconds. This is the only component that talks to Postgres and Redis directly.

**Component B — The Developer SDK (Integration Tool).** A lightweight Python package, `agentguard-sdk`, installed via `pip`. Provides wrappers for LangChain and CrewAI (and a plain-Python interface for any other framework) that automatically route an agent's tool calls to the Core Engine instead of executing them locally. The SDK never bypasses the gateway and never contains policy logic itself — it only calls the API and interprets the response.

**Component C — The Control Plane (Web Dashboard).** A Next.js/React web application — the visual "Control Room" for human administrators. Shows a live feed of agent actions, a Human-in-the-Loop approval queue, agent/tool/policy/budget management screens, and an Audit Log viewer that can trigger cryptographic hash-chain verification and show CHAIN VALID / CHAIN INVALID.

## Non-Negotiable Technical Constraints

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Redis, JWT auth, SHA-256 hash chaining, pytest, httpx.
- SDK: Python, httpx, Pydantic, `agentguard-sdk` package, local editable install during development.
- Dashboard: Next.js, React, TypeScript, Tailwind CSS, JWT auth, talks to the backend only via the versioned REST API.
- Infra: Docker + Docker Compose locally; free-tier managed services only (e.g. Neon/Supabase for Postgres, Upstash for Redis, Fly.io/Koyeb for backend, Vercel for frontend) — no paid infrastructure is required or assumed.
- Do not introduce a second database, a message broker other than Redis Streams, Kubernetes, a service mesh, blockchain, custom LLM training, or a rules-DSL. These are explicitly excluded from this project.
- Dangerous tools (`delete_database`, `process_refund`, etc.) are always implemented as safe mock tools. No code path may ever execute a real destructive operation.
- Never claim "100% regulatory compliance." Compliance work documents which controls are satisfied and which would require a real third-party audit — it never asserts certification the project doesn't have.

## Development Order — Follow Exactly, Do Not Reorder

Work phase by phase. Each phase has an exit condition; do not start the next phase until the current one's exit condition is met.

1. **Foundation** — monorepo structure, Docker Compose, health endpoints, CI skeleton.
2. **Database + data model** — SQLAlchemy models and migrations for users, organizations, roles, agents, tools, policies, agent_tool_permissions, budgets, tool_requests, hitl_requests, audit_logs, api_keys.
3. **Auth + RBAC** — registration, login, JWT, roles (ADMIN, SECURITY, AUDITOR, MANAGER, DEVELOPER), organization isolation, API keys for agents.
4. **Agents + tools registry** — CRUD for agents and tools, risk levels (LOW/MEDIUM/HIGH/CRITICAL), permission assignment.
5. **Policy engine** — the 9-step deterministic pipeline: AUTH → AGENT STATUS → TOOL PERMISSION → POLICY → RATE LIMIT → BUDGET → RISK → HITL → FINAL DECISION. Every branch unit-tested.
6. **Redis rate limiting + cost guard** — sliding-window request/token counters, session and daily budget caps.
7. **Pre-dispatch gateway** — `POST /guard/check`. Blocked requests never reach the mock tool. Every decision writes an audit event before the response returns.
8. **Cryptographic audit vault** — hash-chained log (`current_hash = SHA256(previous_hash + event_data)`), verification endpoint, tamper detection.
9. **Human-in-the-Loop engine** — PENDING → APPROVED/DENIED → resume/stop, with expiration.
10. **Python SDK** — `client.py`, `models.py`, `exceptions.py`, `guard.py`; exceptions for Denied, Pending, AuthenticationError, Timeout, ServerError.
11. **Framework-agnostic demo** — the same guard/check contract proven against a plain Python agent, a LangChain-style agent, and a simulated agent.
12. **Backend dashboard APIs** — auth, agents, tools, policies, budgets, guard, hitl, audit, monitoring endpoints, fully matching the frozen OpenAPI contract.
13. **Control Plane dashboard** — Dashboard, Agents, Tools, Policies, Budgets, Approvals, Audit Vault, Settings screens, wired to real backend data only.
14. **Real-time activity feed** — polling first; WebSocket/SSE only if time permits later.
15. **Security hardening** — RBAC/org-isolation attack testing, secrets scanning, CORS, input validation.
16. **Testing** — unit, integration, and end-to-end coverage across every phase above, minimum 80% unit / 60% integration.
17. **Observability** — structured logs (request_id, agent_id, organization_id, decision, latency_ms), `/health`, `/ready`.
18. **Performance** — benchmark at 100/500/1000/5000 guard requests, report p95/p99 honestly with test conditions attached.
19. **End-to-end demo scenario** — the FinanceAgent refund flow, start to finish, including a denied CRITICAL action and a chain verification.
20. **Deployment** — free-tier staging environment, atomic-deploy rollout with instant rollback, DR runbook (RPO < 1hr, RTO < 4hr).
21. **SDK packaging** — `pyproject.toml`, versioning, docs, publish-ready.
22. **Documentation** — README plus `docs/architecture.md`, `api.md`, `sdk.md`, `security.md`, `audit.md`, `hitl.md`, `deployment.md`, `demo.md`.
23. **Final quality audit** — walk every checklist (product, security, policy, audit, HITL, SDK, frontend, deployment, docs) before calling anything done.

## Final Outcome / Definition of Done

The project is complete when this exact flow works end to end: an AI agent proposes a tool call → the SDK sends it to the Guard API → authentication, RBAC, tool permission, policy, rate limit, budget, and risk checks all run in order → the result is ALLOW, DENY, or PENDING → the decision is written to the hash-chain audit log → if PENDING, a human approves or denies it from the Control Plane and the agent resumes or stops accordingly → a safe mock tool executes only after ALLOW → an auditor can click "Verify Chain" in the dashboard and get CHAIN VALID, and get CHAIN INVALID if any log was tampered with.

The three components (Core Engine, SDK, Control Plane) are the deliverable — not a single-file demo, not a UI mockup with fake data, and not a claim of enterprise scale or certified compliance the project hasn't actually earned.

## Golden Rule

The agent can propose. AgentGuard decides. The tool executes only after AgentGuard allows it. Every decision is recorded. High-risk decisions require a human. The audit trail can be cryptographically verified. If you find yourself about to build something that doesn't serve one of these five sentences, stop and ask before continuing.
