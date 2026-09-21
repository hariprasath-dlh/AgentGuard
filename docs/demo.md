# Demo Guide: FinanceAgent Governance Scenario

This document explains the canonical AgentGuard demo scenario and provides step-by-step instructions for reproducing it on a fresh local stack.

---

## What the Demo Proves

The FinanceAgent scenario is a single-agent workflow that exercises all five governance guarantees in sequence:

| Step | Tool | Risk | Decision | Guarantee Exercised |
|------|------|------|----------|---------------------|
| 1 | `read_customer` | LOW | ALLOW | Pre-dispatch interception + normal execution |
| 2 | `send_email` | MEDIUM | ALLOW | Medium-risk tools pass policy |
| 3 | `process_refund` | HIGH | PENDING | HITL queue for high-risk actions |
| 4 | Manager approves | — | APPROVED | Human-in-the-loop resume flow |
| 5A | `delete_database` (no permission) | CRITICAL | DENY | Basic permission check |
| 5B | `delete_database` (with permission) | CRITICAL | DENY | **CRITICAL override invariant** |
| 6 | `POST /audit/verify` | — | CHAIN VALID | Cryptographic hash-chain verification |

Step 5B is the most important: it proves that even when an agent has been explicitly granted permission for a CRITICAL tool, the risk policy still denies the call. Permission grants do not override CRITICAL-risk rules.

---

## Reference: Phase 19 Execution Evidence

The canonical execution of this scenario is documented in [`docs/demo-recording/phase19-complete.md`](demo-recording/phase19-complete.md), executed 2026-09-17 against a local PostgreSQL 15 + Redis 7 stack.

Key results from that execution:
- Organization: `agentguard-demo` / `id=1b0c084d-0f59-4afa-ae4c-705e6168a7b5`
- Agent: `FinanceAgent` / `id=026ed85a-dab4-4773-aeb4-f027c0b73f80`
- Step 3 PENDING request_id: `5cf226bd-4482-4c5a-80e7-d054ae32a821`
- Step 4 refund confirmation: `REF-F0F0AEFE` (mock output)
- Step 6 chain verification: `VALID` across 20 records
- Step 5B DENY reason: `"Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy."`

---

## Prerequisites

A running local stack:
- Backend at `http://localhost:8000`
- Redis at `localhost:6379`
- PostgreSQL at `localhost:5432` **or** SQLite fallback (acceptable for demo purposes)

```bash
# Start infrastructure
docker compose up -d postgres redis

# Start backend (from backend/)
uvicorn app.main:app --reload --port 8000

# Optional: start frontend (from frontend/)
npm run dev
```

---

## Step-by-Step Demo Instructions

### 1. Set Up the Demo Organization

Run the demo setup script to create all required users, agents, tools, and permissions:

```bash
cd demo
python run_demo_scenario.py
```

This creates:
- Organization `agentguard-demo`
- Users: `admin@agentguard-demo.local` (ADMIN), `manager@agentguard-demo.local` (MANAGER), `auditor@agentguard-demo.local` (AUDITOR)
- Agent: `FinanceAgent` with an API key
- Tools: `read_customer` (LOW), `send_email` (MEDIUM), `process_refund` (HIGH), `delete_database` (CRITICAL)
- Permissions for FinanceAgent on `read_customer`, `send_email`, `process_refund`
- **Note:** `delete_database` is intentionally NOT granted at setup time

The script prints the API key and agent ID at the end — save these.

### 2. Set Environment Variables for the SDK

```bash
# These come from the output of run_demo_scenario.py
export AGENTGUARD_API_KEY="ag_live_..."
export AGENTGUARD_AGENT_ID="..."
export AGENTGUARD_BASE_URL="http://localhost:8000/api/v1"
```

### 3. Run the Full Demo Script

```bash
cd demo
python run_all.py
```

This script executes all 6 steps in sequence, printing results for each.

Expected output:

```
=== Step 1: read_customer (LOW risk) ===
✓ ALLOW — request_id: c3c3b331-...
  Executed: {"customer_id": "CUST-9921", "name": "Jane Doe", ...}

=== Step 2: send_email (MEDIUM risk) ===
✓ ALLOW — request_id: 5ab974c0-...
  Executed: {"message_id": "MSG-...", "status": "sent"}

=== Step 3: process_refund (HIGH risk) ===
⏸ PENDING — request_id: 5cf226bd-...
  Reason: Action on tool 'process_refund' requires human approval (HITL).
  *** Agent paused. Open the Control Plane to approve. ***

=== HITL APPROVAL (automated for demo) ===
  Approving via API as manager@agentguard-demo.local...
✓ APPROVED — refund_id: REF-F0F0AEFE

=== Step 5A: delete_database (no permission) ===
✗ DENY — Agent 'FinanceAgent' has no permission grant for tool 'delete_database'.

=== Step 5B: delete_database (with explicit permission) ===
  Granting explicit permission for delete_database...
✗ DENY — Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy.
  CRITICAL override confirmed: permission grants cannot override CRITICAL risk policy.

=== Step 6: Verify Audit Chain ===
✓ CHAIN VALID — 20 records verified, 0 tampering detected
```

### 4. Observe the HITL Flow in the Control Plane (Optional)

Instead of letting `run_all.py` auto-approve in Step 4, pause it after Step 3 and use the dashboard:

1. Open `http://localhost:3000` in a browser
2. Log in as `manager@agentguard-demo.local`
3. Navigate to **Approvals** in the sidebar
4. Find the pending `process_refund` request
5. Click **Approve** and add a review note
6. Observe the request move to APPROVED

### 5. Verify the Audit Chain in the Dashboard

1. Log out from the manager account
2. Log in as `auditor@agentguard-demo.local`
3. Navigate to **Audit Vault** in the sidebar
4. Observe the hash chain visual showing all records
5. Click **Verify Chain**
6. Observe the sweep animation and the **CHAIN VALID** result

---

## Reproducing from Scratch

If you want a completely clean run (no data from previous runs):

```bash
# Stop everything
docker compose down

# Delete volumes (clears PostgreSQL data)
docker compose down -v

# Restart infrastructure
docker compose up -d postgres redis

# Wait for PostgreSQL to be ready (~5 seconds)
sleep 5

# Restart backend (creates fresh SQLite or runs Alembic migrations)
uvicorn app.main:app --reload --port 8000 &

# Re-run demo setup
cd demo
python run_demo_scenario.py
python run_all.py
```

---

## Demo Scenario: What Each Step Verifies

### Step 1 — READ CUSTOMER (LOW risk, ALLOW)

The agent proposes `read_customer`. The policy engine evaluates:
- AUTH ✓ (valid API key)
- AGENT STATUS ✓ (FinanceAgent is ACTIVE)
- TOOL PERMISSION ✓ (explicit grant exists)
- TOOL ENABLED ✓ (is_active=true)
- ACTION ALLOWED ✓ (action = "execute")
- RISK LEVEL ✓ (LOW → ALLOW)
- BUDGET ✓ (within caps)
- RATE LIMIT ✓ (within window)
- HITL ✓ (no HITL required)
- PROHIBITED PARAMS ✓ (no patterns matched)
- SUSPICIOUS REQUEST ✓ (small payload)

Result: ALLOW. Mock handler returns a fake customer profile. Audit record #1 written.

### Step 2 — SEND EMAIL (MEDIUM risk, ALLOW)

Same pipeline. MEDIUM risk maps to ALLOW in the default RISK policy. Audit record #2 written.

### Step 3 — PROCESS REFUND (HIGH risk, PENDING)

At step 6, risk level HIGH maps to HITL. After all 11 checks pass, the engine returns PENDING. The gateway creates a `HITLRequest` with a 24-hour expiration. Audit record #3 written with `decision = "PENDING"`.

The agent's SDK raises `AgentGuardPending`. The agent pauses.

### Step 4 — MANAGER APPROVAL

A user with the MANAGER role calls `POST /api/v1/hitl/{id}/approve`. The commit-before-execute sequence:
1. Status updated to APPROVED
2. Audit record #4 (`HITL_APPROVED`) written and committed
3. `process_refund` mock handler executes
4. Audit record #5 (`TOOL_EXECUTED`) written
5. Response returned with `refund_id = "REF-..."` in `output_payload`

### Step 5A — DELETE DATABASE (no permission, DENY)

The policy engine fails at Step 3 (TOOL PERMISSION). No permission grant exists. DENY is returned immediately without reaching the risk level check. Audit record written.

### Step 5B — DELETE DATABASE (explicit permission, DENY)

An ADMIN grants `is_allowed=true` for FinanceAgent on `delete_database`. The agent re-attempts the call:
- Steps 1–3: PASS (auth, agent status, permission)
- Step 4–5: PASS (tool enabled, action non-empty)
- **Step 6: FAIL** — `delete_database` has `risk_level = "CRITICAL"`, the RISK policy maps CRITICAL → DENY

The engine returns DENY **before** the agent even reaches the budget or HITL checks. The explicit permission grant at step 3 is overridden by the risk policy at step 6. This is structural — it cannot be bypassed by permission configuration.

### Step 6 — AUDIT CHAIN VERIFICATION

An AUDITOR calls `POST /api/v1/audit/verify`. The verifier reads all records for the organization ordered by `sequence_number ASC` and:
- Checks each sequence number is gapless
- Checks each `previous_hash` matches the prior record's `current_hash`
- Recomputes each `current_hash = SHA256(previous_hash + canonical_data)` and compares to stored value

All 20 records pass. Status: CHAIN VALID.

---

## Troubleshooting

**`AgentGuardAuthenticationError` on guard/check:**
- API key may have been revoked or expired
- Re-run `run_demo_scenario.py` to generate a new key

**`PENDING` decision not appearing in the Approvals screen:**
- Check that you're logged in as MANAGER or ADMIN (AUDITOR/DEVELOPER cannot see HITL requests)
- Check that the request hasn't already expired (24-hour window)

**`CHAIN INVALID` on verification:**
- If you manually edited a database record to test tampering, this is expected
- Drop and recreate the database for a clean run

**Backend fails to start:**
- Check `DATABASE_URL` and `REDIS_URL` environment variables
- Verify Docker containers are running: `docker compose ps`
