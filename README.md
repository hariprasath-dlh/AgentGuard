# AgentGuard

**Framework-Agnostic Runtime Governance and Policy Enforcement Layer for Autonomous AI Agents**

[![Build Status](https://github.com/hariprasath-dlh/AgentGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/hariprasath-dlh/AgentGuard/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/agentguard-governance-sdk.svg)](https://pypi.org/project/agentguard-governance-sdk/)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%20%3E%3D3.9-blue.svg)](https://www.python.org/)
[![Node Version](https://img.shields.io/badge/node-20.x-green.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AgentGuard is a pre-dispatch security and governance control plane that sits between an autonomous AI agent and the external tools, APIs, and databases it attempts to execute. By acting as an authoritative runtime proxy, AgentGuard intercepts every proposed tool invocation, validates it against role-based access control (RBAC), token/financial spend budgets, rate limits, and risk policies, and issues an explicit decision: **ALLOW**, **DENY**, or **PENDING**. High-risk operations halt for asynchronous human-in-the-loop (HITL) approval, and every event is cryptographically sealed into a SHA-256 hash-chained, tamper-evident audit vault.

> **The Golden Rule of Agent Governance:**  
> *The agent proposes. AgentGuard decides. The tool executes only after AgentGuard allows it.*

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Our Solution](#our-solution)
- [What Already Exists, and What This Fills](#what-already-exists-and-what-this-fills)
- [Key Features](#key-features)
  - [Platform Governance Engine](#platform-governance-engine)
  - [Control Plane Web Dashboard](#control-plane-web-dashboard)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
  - [Decision Pipeline Request Flow](#decision-pipeline-request-flow)
  - [Component Architecture](#component-architecture)
- [Local Installation and Setup](#local-installation-and-setup)
- [Setting Up AgentGuard in Your Own Project](#setting-up-agentguard-in-your-own-project)
- [Using the Python SDK](#using-the-python-sdk)
- [Running and Connecting Everything Together](#running-and-connecting-everything-together)
- [Demo Credentials and Quick Start](#demo-credentials-and-quick-start)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [Security Model](#security-model)
- [Engineering Challenges and How They Were Resolved](#engineering-challenges-and-how-they-were-resolved)
- [Roadmap and Future Work](#roadmap-and-future-work)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments and Contact](#acknowledgments-and-contact)

---

## Problem Statement

As autonomous AI agents transition from passive chatbots into active execution engines interacting with databases, internal microservices, payment gateways, and third-party APIs, enterprises face critical runtime governance failures that traditional infrastructure cannot prevent:

1. **Runaway Agent Costs:** Without pre-dispatch rate limiters and real-time spend ceilings, looping agents can trigger thousands of LLM or third-party API invocations within minutes, generating catastrophic infrastructure bills.
2. **Unrestricted Tool Execution:** Multi-tenant agents frequently run with monolithic credentials. If an agent hallucinates, experiences prompt injection, or deviates from intent, it can issue destructive shell commands (`rm -rf`) or data-wiping SQL statements (`DROP TABLE`) without an independent enforcement boundary.
3. **Absence of Pre-Dispatch Governance:** Traditional agent frameworks focus on agent construction, orchestration, and prompting. They evaluate logic before calling an LLM, but once the agent outputs a tool invocation, execution is dispatched directly to client code without an external policy gatekeeper.
4. **Non-Compliant, Mutable Audit Trails:** Regulatory frameworks (including EU AI Act Article 12, HIPAA, and SOC2) demand unalterable, non-repudiable logs of autonomous decisions. Standard database logs and application logging services can be updated, truncated, or dropped by anyone with database access, failing evidentiary compliance.
5. **Missing Asynchronous Human-in-the-Loop (HITL):** High-stakes actions (such as processing refunds or database operations) should not be automated blindly. Existing systems lack structured, asynchronous workflow suspension where an agent pauses execution, awaits human review via a secure dashboard, and resumes only after explicit approval.

---

## Our Solution

AgentGuard delivers an out-of-process, deterministic runtime governance boundary designed specifically for AI agent tool execution:

- **Pre-Dispatch Interception Model:** No tool invocation reaches external infrastructure without passing through `POST /api/v1/guard/check`. The core engine acts as a stateful bouncer that intercepts the structured payload, verifies caller identity, checks policy rules, and registers the attempt before returning an authoritative decision.
- **The Golden Rule:** The agent never executes tools optimistically. The agent proposes parameters, AgentGuard evaluates constraints, and the tool executes only when AgentGuard returns `ALLOW`.
- **Three-Component Decoupled Architecture:**
  1. **Core Engine (Backend API):** A FastAPI microservice backed by PostgreSQL and Redis. It evaluates tool invocations through an 11-step deterministic policy pipeline and appends records to the audit vault.
  2. **Python SDK (`agentguard-governance-sdk`):** A lightweight client distributed on PyPI that wraps agent tool dispatches in simple, idiomatic Python methods with automatic retry handling, timeout enforcement, and structured exceptions.
  3. **Control Plane (Web Dashboard):** A modern React 19 web interface powered by TanStack Router and Vite, allowing administrators, compliance auditors, and security officers to inspect live telemetry, approve/deny pending HITL requests, configure policies, and verify cryptographic audit chains.

---

## What Already Exists, and What This Fills

| Capability / Requirement | Observability Platforms (e.g., LangSmith, Langfuse) | Traditional API Gateways (e.g., Kong, AWS API Gateway) | AgentGuard Governance Control Plane |
| :--- | :--- | :--- | :--- |
| **Enforcement Timing** | **Post-hoc logging:** Records what the agent did after execution occurred. Cannot block a destructive action before it runs. | **Edge network filtering:** Inspects raw HTTP endpoints, but lacks awareness of agent identity, tool semantics, or model parameters. | **Pre-dispatch blocking:** Evaluates structured tool arguments before the tool client executes. Blocks or pauses calls in flight. |
| **Audit Log Integrity** | **Mutable application storage:** Database rows can be updated, deleted, or purged. | **Standard access logs:** Text/JSON log files stored in cloud log groups; susceptible to retention purges or alteration. | **Cryptographic Hash Chain:** Tamper-evident SHA-256 block chain linked per organization with genesis hashing and zero-knowledge verification. |
| **Contract & Integration** | **Framework lock-in:** Requires importing specific LLM wrappers or tracer instrumentations. | **Network infrastructure:** Requires DNS routing, complex reverse proxies, and infrastructure provisioning. | **Framework-agnostic HTTP/JSON:** Plain HTTP contract compatible with any agent framework (LangChain, CrewAI, AutoGen, or custom loops). |
| **Human Oversight (HITL)** | **None:** Read-only tracing and observability dashboards. | **None:** Binary HTTP routing without asynchronous review workflows. | **Native Asynchronous HITL:** Suspends execution, issues `PENDING` tokens, alerts operators, and resumes upon signed approval. |
| **Risk Overrides** | **None:** Observability only. | **Static route rules:** Rate limits by IP or generic API key. | **Deterministic Invariant:** Hard-blocks `CRITICAL` risk operations regardless of user-defined overrides. |

---

## Key Features

### Platform Governance Engine

- **Strict Multi-Tenant RBAC:** Supports five distinct organization roles (`ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`, `DEVELOPER`) with fine-grained endpoint authorization and organization data isolation.
- **11-Step Deterministic Evaluation Pipeline:** Pure-logic, zero-LLM decision flow guaranteeing explainable, reproducible decisions under 15ms.
- **Dual-Layer Resource Controls:** Redis sliding-window rate limiters combined with PostgreSQL-backed token and monetary spend budgets.
- **Tamper-Evident SHA-256 Audit Vault:** Every evaluation produces an immutable audit record chained to the organization's prior block hash. The system provides an automated chain verification endpoint (`GET /api/v1/audit/verify-chain`) that detects insertions, deletions, or data modifications.
- **Asynchronous HITL Workflow:** High-risk actions transition to `PENDING`, generating review requests in the human operator queue with customizable timeout limits and audit rationale logging.
- **Dual Authentication Vectors:** Supports email/password authentication alongside production-grade Google OAuth 2.0 with state CSRF verification and hashed API keys (`ag_live_...`).

### Control Plane Web Dashboard

The Control Plane provides eight purpose-built screens accessible by role:

1. **Dashboard (`/dashboard`):** Real-time operational overview displaying total evaluated requests, approval/denial ratios, active agent counts, system health, and recent security alerts.
2. **Agents Management (`/agents`):** Central registry displaying registered autonomous agents, active/paused lifecycle statuses, assigned policy profiles, and token budget allocations.
3. **Tools Catalog (`/tools`):** Complete catalog of registered agent tools, their risk classifications (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), parameter schemas, and enable/disable toggles.
4. **Policies Editor (`/policies`):** Rule engine interface for configuring risk thresholds, prohibited regex patterns, automated actions, and custom risk-tier mappings.
5. **Approvals Queue (`/approvals`):** Dedicated Human-in-the-Loop triage center for reviewing pending requests, inspecting execution parameters, and submitting approvals or rejections with required reason notes.
6. **Audit Vault Viewer (`/audit`):** Cryptographic ledger explorer displaying sequence numbers, previous/current SHA-256 hashes, timestamps, and an interactive **Verify Chain** tool to audit ledger integrity.
7. **Budgets & Spend Tracker (`/budgets`):** Live monitoring interface displaying hourly/daily token consumption, dollar-denominated spend caps, and budget threshold alerts.
8. **Settings & Access Management (`/settings`):** Organization management panel for generating and revoking API keys, administering user accounts, inspecting role permissions, and viewing API credentials.

---

## Technology Stack

| Technology | Component | Rationale for Choice |
| :--- | :--- | :--- |
| **FastAPI** | Core Engine | High-performance Python async web framework providing native OpenAPI generation and sub-millisecond route dispatching. |
| **Pydantic v2** | Core Engine & SDK | Rust-backed data validation and serialization ensuring strict schema validation and ultra-fast serialization for high-throughput governance. |
| **SQLAlchemy 2.0** | Core Engine | Robust ORM providing explicit transaction boundaries, migration safety, and row-level locking (`SELECT ... FOR UPDATE`) needed for audit sequence integrity. |
| **PostgreSQL 15** | Database | ACID-compliant relational storage for relational entity graphs, organization multi-tenancy, and audit vault ledger persistence. |
| **Redis 7** | Cache & Limiting | In-memory key-value engine with append-only persistence providing high-concurrency sliding-window rate limiting and active session management. |
| **React 19** | Control Plane | Latest React core utilizing modern concurrent rendering and optimized component lifecycles for responsive UI interaction. |
| **TanStack Router & Query** | Control Plane | Type-safe client-side routing combined with asynchronous server-state synchronization, query caching, and optimistic updates. |
| **Vite 8 & TailwindCSS 4** | Control Plane | Next-generation build tooling delivering sub-second hot-reloads and utility-first styling with zero runtime CSS overhead. |
| **httpx** | Python SDK | Modern HTTP client supporting connection pooling, timeout configurations, and connection retry backoffs. |
| **Docker & Compose** | Infrastructure | Standardized containerization ensuring identical development, testing, and production service environments. |
| **Playwright** | Testing | Headless browser automation providing full cross-role E2E testing across desktop and mobile viewports. |
| **Pytest & Ruff** | Backend & SDK | Python testing suite and lightning-fast linter/formatter enforcing strict type safety, code hygiene, and separate coverage gates. |

---

## System Architecture

### Decision Pipeline Request Flow

The following sequence details how an agent's proposed tool invocation travels from the SDK through AgentGuard's 11-step evaluation pipeline before any tool code executes:

```mermaid
sequenceDiagram
    autonumber
    actor Agent as Autonomous Agent
    participant SDK as AgentGuard SDK
    participant GW as Guard Gateway (POST /guard/check)
    participant PE as Policy Engine (11 Steps)
    participant Redis as Redis (Limits & Budget)
    participant Vault as Audit Vault (PostgreSQL)
    participant HITL as Approvals Queue (Dashboard)
    actor Human as Human Operator
    participant Tool as Target Tool / API

    Agent->>SDK: execute_tool(name, params)
    SDK->>GW: POST /api/v1/guard/check (API Key + Payload)
    
    rect rgb(240, 245, 255)
        note over PE: Deterministic 11-Step Pipeline
        GW->>PE: 1. AUTH (Caller Identity)
        PE->>PE: 2. AGENT STATUS (Active/Paused)
        PE->>PE: 3. TOOL PERMISSION (Agent allowed tool?)
        PE->>PE: 4. TOOL ENABLED (Tool active in registry?)
        PE->>PE: 5. ACTION ALLOWED (Action supported?)
        PE->>PE: 6. RISK LEVEL (LOW / MED / HIGH / CRITICAL)
        PE->>Redis: 7. BUDGET (Check token & monetary limits)
        PE->>Redis: 8. RATE LIMIT (Sliding-window counters)
        PE->>PE: 9. HITL CHECK (Flagged for human review?)
        PE->>PE: 10. PROHIBITED PARAMS (Regex denylist inspection)
        PE->>PE: 11. SUSPICIOUS REQUEST (Payload size & anomalies)
    end

    PE->>Vault: Write SHA-256 chained audit record (SELECT FOR UPDATE)
    
    alt Decision: ALLOW
        PE-->>SDK: 200 OK {"decision": "ALLOW", "allowed": true}
        SDK-->>Agent: Return GuardResult(allowed=True)
        Agent->>Tool: Execute real tool payload
    else Decision: DENY (Risk, Rule, or Prohibited Input)
        PE-->>SDK: 200 OK {"decision": "DENY", "allowed": false}
        SDK-->>Agent: Raise AgentGuardDenied(reason, request_id)
    else Decision: PENDING (High Risk / HITL Triggered)
        PE-->>HITL: Create Pending Request in Queue
        PE-->>SDK: 200 OK {"decision": "PENDING", "allowed": false}
        SDK-->>Agent: Raise AgentGuardPending(request_id)
        Human->>HITL: Review params and approve/deny
        HITL->>Vault: Append approval decision to audit chain
    end
```

### Component Architecture

```mermaid
graph TD
    subgraph Client Application
        Agent[Autonomous Agent Logic]
        SDK[agentguard-governance-sdk]
        Agent -->|guard call| SDK
    end

    subgraph AgentGuard Core Engine
        Gateway[FastAPI Ingress Router]
        PolicyEngine[11-Step Deterministic Policy Engine]
        VaultService[Cryptographic Audit Vault Service]
        AuthService[RBAC & OAuth Security Layer]
        
        Gateway --> AuthService
        Gateway --> PolicyEngine
        PolicyEngine --> VaultService
    end

    subgraph State & Storage Tier
        PG[(PostgreSQL 15)]
        RD[(Redis 7)]
        
        AuthService --> PG
        PolicyEngine --> RD
        VaultService -->|SHA-256 Hash Chain| PG
    end

    subgraph Operator Control Plane
        Dashboard[Web Control Plane React 19 / Vite]
        HITLQueue[HITL Approvals Queue]
        AuditExplorer[Audit Chain Explorer]
        
        Dashboard --> Gateway
        Dashboard --> HITLQueue
        Dashboard --> AuditExplorer
    end

    SDK -->|HTTP / JSON| Gateway
```

---

## Local Installation and Setup

### Prerequisites

- **Docker & Docker Compose** (Docker Desktop 4.x+ recommended)
- **Python 3.11+**
- **Node.js 20.x+** and **npm**

### 1. Clone the Repository

```bash
git clone https://github.com/hariprasath-dlh/AgentGuard.git
cd AgentGuard
```

### 2. Configure Environment Variables

Copy the provided environment template to `.env`:

```bash
cp .env.example .env
```

The default configuration is ready for local development:

```ini
DATABASE_URL=postgresql://agentguard:agentguard_password@localhost:5432/agentguard
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-here
API_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:8080
FRONTEND_URL=http://localhost:8080
AGENTGUARD_ENV=development
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

### 3. Start PostgreSQL and Redis

Start the backing infrastructure using Docker Compose:

```bash
docker compose up -d postgres redis
```

Verify the containers are healthy:

```bash
docker compose ps
```

### 4. Set Up the Backend Environment

Create a virtual environment, install backend dependencies, apply database migrations, and seed the demo dataset:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

On Linux / macOS:
```bash
source .venv/bin/activate
```

On Windows (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Apply database migrations:
```bash
alembic upgrade head
```

Run the idempotent database seeder:
```bash
python -m app.core.seed
```

Start the backend API server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Verify Backend Health

In a separate terminal, confirm the backend is running:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

```bash
curl http://localhost:8000/ready
```

Expected response:
```json
{"status": "ready"}
```

### 6. Set Up and Launch the Control Plane (Frontend)

In a separate terminal, install dependencies and launch the frontend dashboard:

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be live at `http://localhost:8080`.

---

## Setting Up AgentGuard in Your Own Project

Integrating AgentGuard into an existing agent application requires three straightforward steps:

### Step 1: Register Your Tools and Agent

Access the Control Plane at `http://localhost:8080` (or use the REST API) to register your tools and agent:

1. **Register Tools:** Go to **Tools** (`/tools`) and register each tool your agent can invoke. Assign an appropriate risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
2. **Register Agent:** Go to **Agents** (`/agents`) and create your agent profile (e.g., `SupportAgent`, `FinanceAgent`).
3. **Assign Permissions:** Grant your agent permission to execute specific registered tools.
4. **Generate API Key:** In **Settings** (`/settings`), create a dedicated API key (`ag_live_...`) for your application.

### Step 2: Install the Governance SDK

In your agent's Python project environment, install the SDK from PyPI:

```bash
pip install agentguard-governance-sdk
```

### Step 3: Wrap Tool Invocations

Wrap your agent's tool execution logic with `client.guard(...)` before calling the underlying tool:

```python
import os
from agentguard import AgentGuard, AgentGuardDenied, AgentGuardPending

# Initialize client with your AgentGuard instance URL and API Key
guard_client = AgentGuard(
    api_key=os.environ["AGENTGUARD_API_KEY"],
    base_url=os.getenv("AGENTGUARD_BASE_URL", "http://localhost:8000/api/v1"),
    agent_id=os.environ["AGENTGUARD_AGENT_ID"]
)

def safe_tool_dispatcher(tool_name: str, arguments: dict):
    try:
        # Pre-dispatch evaluation
        decision = guard_client.guard(tool=tool_name, parameters=arguments)
        if decision.allowed:
            # Execute actual tool logic only after explicit ALLOW
            return execute_actual_tool(tool_name, arguments)
    except AgentGuardDenied as e:
        print(f"Execution blocked by policy: {e.reason} (Request ID: {e.request_id})")
        return {"error": "Action denied by governance policy", "reason": e.reason}
    except AgentGuardPending as e:
        print(f"Action requires human approval. Task ID: {e.request_id}")
        return {"status": "pending_approval", "request_id": e.request_id}
```

---

## Using the Python SDK

The official AgentGuard SDK (`agentguard-governance-sdk`) provides a clean interface for integrating governance checks into any agent framework.

### Installation

```bash
pip install agentguard-governance-sdk
```

### Basic Usage with Exception Handling (Recommended)

By default, `client.guard(...)` operates in strict mode (`raise_for_status=True`), raising explicit exceptions when an operation is blocked or requires approval:

```python
from agentguard import (
    AgentGuard,
    AgentGuardAuthenticationError,
    AgentGuardDenied,
    AgentGuardPending,
    AgentGuardServerError,
    AgentGuardTimeout,
)

client = AgentGuard(
    api_key="ag_live_a1b2c3d4e5f6...",
    base_url="http://localhost:8000/api/v1",
    agent_id="d3b07384-d113-4e44-b040-9a3e3c639fdc",
    timeout=5.0,
    max_retries=1
)

try:
    result = client.guard(
        tool="process_refund",
        parameters={"customer_id": "CUST-9921", "amount": 450.00},
        estimated_cost=450.00,
        estimated_tokens=150,
        metadata={"session_id": "sess_88392"}
    )
    print(f"Tool allowed! Request ID: {result.request_id}")
    # Run the real tool execution here

except AgentGuardDenied as e:
    # Action permanently blocked by policy or critical risk
    print(f"BLOCKED: {e.reason} (Request: {e.request_id})")

except AgentGuardPending as e:
    # High-risk action suspended awaiting human-in-the-loop approval
    print(f"SUSPENDED: Queued for operator review. Tracking ID: {e.request_id}")

except AgentGuardAuthenticationError as e:
    # Invalid or revoked API key
    print(f"AUTH ERROR: Check API credentials: {e}")

except AgentGuardTimeout as e:
    # Network unreachable or gateway timed out
    print(f"TIMEOUT: Governance engine did not respond in time: {e}")

except AgentGuardServerError as e:
    # Backend returned a 5xx error
    print(f"SERVER ERROR: Governance backend issue: {e}")

finally:
    client.close()
```

### Context Manager & Boolean Branching Mode

For workflows that prefer non-raising boolean checks, set `raise_for_status=False`:

```python
from agentguard import AgentGuard

with AgentGuard(api_key="ag_live_sample", base_url="http://localhost:8000/api/v1") as client:
    result = client.guard(
        tool="read_customer",
        parameters={"customer_id": "CUST-1001"},
        raise_for_status=False
    )

    if result.allowed:
        print(f"Approved to proceed with {result.decision}")
    else:
        print(f"Rejected or Pending: decision={result.decision}, reason={result.reason}")
```

---

## Running and Connecting Everything Together

AgentGuard operates as a coordinated distributed system. Here is how each service runs and connects:

```
Terminal 1: Backend API Service          Terminal 2: Frontend Control Plane        Terminal 3: External Agent Script
-------------------------------          ----------------------------------        ---------------------------------
cd backend                               cd frontend                               cd /path/to/my-agent
uvicorn app.main:app --port 8000         npm run dev --port 8080                   python agent_worker.py
     ▲                                        ▲                                         │
     │                                        │                                         │
     │ (REST API & Health: http://localhost:8000)                                       │
     └────────────────────────────────────────┴─────────────────────────────────────────┘
                                           (HTTP JSON: POST /api/v1/guard/check)
```

| Service | Host / Port | Environment Configuration | Purpose |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | `localhost:5432` | `POSTGRES_USER=agentguard` | Relational storage & cryptographic audit chain ledger |
| **Redis** | `localhost:6379` | `REDIS_URL=redis://localhost:6379/0` | Sliding-window rate limit counters & budget trackers |
| **Core Engine** | `http://localhost:8000` | `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` | Interception API (`/api/v1/guard/check`), policy engine, and auth |
| **Control Plane** | `http://localhost:8080` | `VITE_API_URL=http://localhost:8000/api/v1` | Web UI for administrators, auditors, and HITL reviewers |
| **Agent Script** | External process | `AGENTGUARD_BASE_URL=http://localhost:8000/api/v1` | Any autonomous agent calling `client.guard(...)` over HTTP |

---

## Demo Credentials and Quick Start

> [!WARNING]
> The seeded demo accounts listed below are strictly for local development and integration testing. They must **never** be deployed to staging or production environments.

The database seeder (`python -m app.core.seed`) creates the demo organization (`agentguard-demo`) and five role-specific testing accounts:

| Role | Email Address | Password | Permissions Scope |
| :--- | :--- | :--- | :--- |
| **ADMIN** | `admin@agentguard-demo.local` | `DemoAdmin1!` | Full system administration, API keys, org settings, user roles |
| **SECURITY** | `security@agentguard-demo.local` | `DemoSecurity1!` | Policy configuration, risk limits, prohibited pattern rules |
| **AUDITOR** | `auditor@agentguard-demo.local` | `DemoAuditor1!` | Read-only access to audit logs, telemetry, and chain verification |
| **MANAGER** | `manager@agentguard-demo.local` | `DemoManager1!` | Budget allocations, spend monitoring, HITL approvals |
| **DEVELOPER** | `developer@agentguard-demo.local` | `DemoDeveloper1!` | Agent and tool registration, telemetry inspection |

### Guided Quick Start: The 3-Minute Governance Tour

1. Open `http://localhost:8080` and log in as `admin@agentguard-demo.local` with password `DemoAdmin1!`.
2. Navigate to **Tools** (`/tools`) to inspect the seeded tools:
   - `read_customer` (`LOW` risk &mdash; executes automatically)
   - `send_email` (`MEDIUM` risk &mdash; executes automatically)
   - `process_refund` (`HIGH` risk &mdash; pauses for HITL approval)
   - `delete_database` (`CRITICAL` risk &mdash; hard-denied by invariant)
3. Navigate to **Approvals** (`/approvals`) to view seeded pending approval requests. Approve a pending refund with a review comment.
4. Navigate to **Audit Vault** (`/audit`) and click **Verify Chain** to cryptographically validate the SHA-256 hash ledger across all recorded events.

---

## Testing

AgentGuard maintains a multi-tier testing discipline. Database tests execute against real PostgreSQL and Redis instances; silent database fallbacks are permanently disabled to prevent race-condition masking.

### Test Counts and Coverage Summary

| Test Suite | Tier | Test Count | Minimum Coverage Gate | Verified Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Pure Logic** | Unit | **43 tests** | `≥ 40%` | Passing (Pure logic: schemas, security, stateless checks) |
| **Backend DB & API** | Integration | **237 tests** | `≥ 80%` | Passing (**93%+** actual coverage against real Postgres & Redis) |
| **SDK Suite** | Integration | **13 tests** | N/A | Passing (Real HTTP transport, retry logic, error mappings) |
| **Control Plane E2E** | Playwright | **27 tests** | N/A | Passing (7 test suites: auth, rbac, screens, critical overrides) |

### 1. Running Backend Unit Tests (Pure Logic)

Pure logic tests require no database or network connectivity and execute in seconds:

```bash
cd backend
PYTHONPATH=. pytest tests/ -m unit -v
```

### 2. Running Backend Integration Tests (Real Postgres & Redis)

Integration tests require running Postgres and Redis instances:

```bash
cd backend
TEST_DATABASE_URL=postgresql://agentguard:agentguard_password@localhost:5432/agentguard REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. pytest tests/ -m integration -v
```

To run with coverage reporting:

```bash
cd backend
TEST_DATABASE_URL=postgresql://agentguard:agentguard_password@localhost:5432/agentguard REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. pytest tests/ -m integration --cov=app --cov-report=term-missing
```

### 3. Running SDK Integration Tests

```bash
cd sdk
TEST_DATABASE_URL=postgresql://agentguard:agentguard_password@localhost:5432/agentguard PYTHONPATH=.:../backend pytest tests/ -v
```

### 4. Running Control Plane Playwright E2E Tests

Ensure both backend (`localhost:8000`) and frontend (`localhost:8080`) are running:

```bash
cd frontend
npx playwright test
```

---

## CI/CD Pipeline

Continuous integration is enforced via GitHub Actions (`.github/workflows/ci.yml`) on all pull requests and pushes to `main`.

### Pipeline Status Checks

Branch protection is active on `main` and strictly requires the following 7 checks to pass before merging:

1. `lint-backend`: Ruff linting and code formatting checks.
2. `typecheck-frontend`: TypeScript strict typechecking (`tsc --noEmit`).
3. `test-backend`: Alembic migration validation, unit test coverage check (`≥ 40%`), and integration test coverage check (`≥ 80%`) against real PostgreSQL 15 and Redis 7 service containers.
4. `test-sdk`: Integration test suite for `agentguard-governance-sdk` against live database containers.
5. `build-frontend`: Production Vite compilation and asset bundle generation.
6. `build-backend-docker`: Docker container image build for backend microservice.
7. `secrets-scan`: Gitleaks static analysis scanning repository history for leaked credentials or tokens.

> [!NOTE]
> Continuous Deployment (CD) is intentionally manual per architectural policy. Passing builds do not deploy automatically. Production releases require explicit operator deployment runbooks. See [docs/deployment.md](file:///d:/agentguard/docs/deployment.md) for full operational deployment procedures.

---

## Security Model

For complete architectural details, threat modeling, and regulatory alignment, refer to the [Security Architecture Document](file:///d:/agentguard/docs/security.md).

- **Multi-Tenant Isolation:** Every database entity, Redis key namespace, and audit chain is scoped by `organization_id`. Tenant cross-contamination is structurally impossible at the query level.
- **The CRITICAL-Risk-Override Invariant:** Tools classified as `CRITICAL` risk (e.g., database drops, firmware flashes) cannot be overridden to `ALLOW` or `HITL` by custom user policies. Step 6 of the policy engine enforces an immutable hard-`DENY`.
- **Tamper-Evident Hash Vault:** Audit logs are linked using monotonic sequence numbers and SHA-256 digests:
  $$\text{Hash}_n = \text{SHA-256}(\text{Hash}_{n-1} + \text{CanonicalJSON}(\text{Event}_n))$$
  The first record links to `GENESIS_HASH` ($0^{64}$). While the database cannot magically prevent unauthorized raw SQL deletions if root DB access is compromised, any modification, omission, or row insertion immediately breaks hash-chain continuity and is flagged during verification.
- **Organization Row-Level Locking:** During audit log writes, the vault acquires an exclusive row lock (`SELECT id FROM organizations WHERE id = :org_id FOR UPDATE`), preventing sequence number race conditions and chain forking under heavy concurrency.
- **OAuth & API Key Hardening:** API keys are hashed with SHA-256 before database storage; plaintext keys are returned once upon generation. Google OAuth 2.0 flows utilize cryptographically signed state parameters to eliminate CSRF risks.

---

## Engineering Challenges and How They Were Resolved

This section documents five critical technical incidents encountered during development, how they were diagnosed, and how they were permanently resolved:

### 1. Silent SQLite Fallback Defeating Audit Vault Concurrency Locks
- **The Issue:** Backend tests originally fell back to an in-memory SQLite database (`sqlite:///:memory:`) whenever `TEST_DATABASE_URL` was unset. Concurrency tests for the audit vault appeared to pass green. However, SQLite does not support PostgreSQL's `SELECT ... FOR UPDATE` row-level locking, silently ignoring the clause and masking race conditions in monotonic sequence generation.
- **Diagnosis:** Running high-concurrency threads against real PostgreSQL revealed duplicate sequence numbers and forked hash chains that never appeared in SQLite test runs.
- **Resolution:** Removed the silent SQLite fallback completely from `backend/tests/conftest.py` and `sdk/tests/conftest.py`. The test configuration now fails loud: if `TEST_DATABASE_URL` is unset or unreachable, it immediately raises a fatal `RuntimeError`, guaranteeing that all tests run against real PostgreSQL concurrency semantics.

### 2. RBAC Table Mislabeling Caught by Live API Probing
- **The Issue:** Early project documentation asserted that RBAC permissions were stored in a flat roles table with global defaults. Relying on written documentation summaries caused discrepancies in endpoint permission checks.
- **Diagnosis:** Direct API probing using role-specific JWT bearer tokens revealed that permissions were scoped per-organization with a composite unique constraint (`uq_roles_org_name`). The code was strictly enforcing multi-tenant organization boundaries while the documentation reflected an obsolete single-tenant design.
- **Resolution:** Reconciled the security architecture to match actual database schemas. All dependency injectors (`get_current_user`, `require_role`) and frontend role gates were verified and documented against live endpoint behavior.

### 3. CORS Preflight Failures and Organization Registration Slug Collisions
- **The Issue:** During frontend-to-backend integration, user registration and login requests failed intermittently in web browsers with generic network errors, despite passing curl tests.
- **Diagnosis:** Two distinct bugs were interacting: (1) browser preflight `OPTIONS` requests were rejected by FastAPI because `CORS_ORIGINS` was strictly matching port `8080` without handling variations, and (2) user re-registration attempts with duplicate organization slugs threw unhandled 500 integrity errors rather than structured 409 responses.
- **Resolution:** Updated `CORSMiddleware` in `app/main.py` to parse comma-separated origin lists with whitespace stripping, and updated the registration pipeline to handle organization slug collisions gracefully with clear client error messages.

### 4. Google OAuth `invalid_client` Container Environment Bleed
- **The Issue:** Rebuilding the backend Docker container caused Google OAuth authorization requests to fail with Google error `401: invalid_client`.
- **Diagnosis:** The containerized backend was picking up default mock credentials from fallback environment variables inside `docker-compose.yml` rather than reading the live OAuth secrets defined in the root `.env` file. The application was communicating with Google using dummy credentials.
- **Resolution:** Restructured `docker-compose.yml` environment variable inheritance to explicitly pass live secrets from the `.env` file into the container while maintaining development fallbacks only when variables are completely omitted.

### 5. Test-Tier Misclassification (The "Unit" Suite Illusion)
- **The Issue:** Early test suites reported dozens of "unit" tests passing in milliseconds. In reality, these tests were importing database models, creating ORM sessions, and running against SQLite, creating a false impression of fast, isolated unit coverage.
- **Diagnosis:** Auditing test fixtures revealed that 9 test files marked with `@pytest.mark.unit` were actually integration tests that touched database state and network models.
- **Resolution:** Performed a clean architectural separation. Reclassified all 237 database-dependent test cases as `@pytest.mark.integration` with an 80% coverage requirement. Created a genuine, pure-logic unit tier of 43 tests targeting schemas, password hashing, JWT signing, and stateless policy engine functions with an independent 40% coverage gate.

---

## Roadmap and Future Work

To maintain security integrity and operational focus, specific capabilities are intentionally out of scope for the current version and prioritized for future releases:

- **Asynchronous SDK Client (`AsyncAgentGuard`):** Native `asyncio` client with connection pooling for high-throughput async agent loops.
- **Streaming Token Governance:** Pre-execution token chunk inspection for bidirectional WebSocket and Server-Sent Event (SSE) streaming tool calls.
- **Decentralized Audit Anchoring:** Periodic Merkle tree root anchoring to external public ledgers or cloud key-management hardware security modules (HSM) for third-party compliance proofs.
- **Dynamic Policy Hot-Reloading:** Redis pub/sub invalidation triggers allowing policy rule updates without restarting worker nodes.
- **Kubernetes Native Operator:** Helm charts and Custom Resource Definitions (CRDs) for deploying AgentGuard clusters in enterprise Kubernetes environments.

---

## Contributing

Contributions to AgentGuard are welcome. Before submitting pull requests, ensure your changes adhere to our testing and code quality standards:

1. **Format and Lint:**
   ```bash
   cd backend && ruff check . && ruff format .
   cd ../frontend && npm run lint
   ```

2. **Execute Full Test Suites:**
   ```bash
   # Backend Unit & Integration Tests
   cd backend
   pytest tests/ -m unit
   pytest tests/ -m integration

   # SDK Tests
   cd ../sdk
   pytest tests/
   ```

3. **Verify CI Checks:**  
   GitHub Actions will automatically run all 7 mandatory status checks (`lint-backend`, `typecheck-frontend`, `test-backend`, `test-sdk`, `build-frontend`, `build-backend-docker`, `secrets-scan`). Branch protection prevents merging if any check fails.

---

## License

AgentGuard is open-source software licensed under the **MIT License**. See the [LICENSE](file:///d:/agentguard/LICENSE) file for complete details.

---

## Acknowledgments and Contact

- **Source Repository:** [https://github.com/hariprasath-dlh/AgentGuard](https://github.com/hariprasath-dlh/AgentGuard)
- **Published PyPI Package:** [https://pypi.org/project/agentguard-governance-sdk/](https://pypi.org/project/agentguard-governance-sdk/)
- **Documentation Runbooks:**
  - [Security Architecture & Threat Model](file:///d:/agentguard/docs/security.md)
  - [Production Deployment Runbook](file:///d:/agentguard/docs/deployment.md)

---
*Built with rigorous engineering for safe, governed autonomous AI agent operations.*
