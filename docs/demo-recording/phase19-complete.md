# Phase 19 — End-to-End Governance Demo Scenario Execution

**Milestone:** Phase 19 (End-to-End Demo Scenario) per `project.md`  
**Execution Timestamp:** 2026-09-17T06:17:47Z  
**Target Environment:** Local PostgreSQL 15 + Redis 7 Stack  
**Organization:** `AgentGuard Demo Organization` (`agentguard-demo`, `id=1b0c084d-0f59-4afa-ae4c-705e6168a7b5`)  
**Agent:** `FinanceAgent` (`id=026ed85a-dab4-4773-aeb4-f027c0b73f80`)  

---

## Executive Summary & Guarantees Proven

This document serves as the canonical consolidation of the 6-step FinanceAgent end-to-end governance lifecycle required by Phase 19 of `project.md`:
1. **Pre-dispatch Interception:** All tool invocations route strictly through `POST /api/v1/guard/check`.
2. **Deterministic Risk Evaluation:**
   - **LOW Risk (`read_customer`):** Evaluated and permitted (`ALLOW`).
   - **MEDIUM Risk (`send_email`):** Evaluated and permitted (`ALLOW`).
   - **HIGH Risk (`process_refund`, INR 75,000):** Flagged for human oversight (`PENDING`).
3. **Human-in-the-Loop (HITL) Workflow:**
   - Manager reviews pending request queue in Control Plane.
   - Manager approves request with note: `"Approved VIP refund per customer agreement"`.
   - Tool execution completes successfully with server-side mock handler (`REF-F0F0AEFE`).
4. **CRITICAL-Risk Policy Override Guarantee:**
   - FinanceAgent attempts `delete_database` without permission grant → `DENY` (Missing Permission).
   - Explicit permission grant added via `POST /api/v1/permissions` (`is_allowed=True`).
   - FinanceAgent attempts `delete_database` WITH permission grant → **`DENY`** with reason: `"Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy."` (CRITICAL risk rule strictly overrides explicit permissions).
5. **Cryptographic Audit Vault Verification:**
   - SHA-256 hash-chain verified across all audit records.
   - Verification status: **`VALID`** (Zero tampering detected, 20/20 records validated).

---

## Step-by-Step Execution Record

### Step 1 — Read Customer Account (LOW Risk)
- **Tool:** `read_customer` (Risk: `LOW`)
- **Parameters:** `{"customer_id": "CUST-9921", "fields": ["name", "email", "balance"]}`
- **Decision:** `ALLOW`
- **Request ID:** `c3c3b331-e570-4ced-a00f-911d313ac384`
- **Reason:** `All policy checks passed.`
- **Client Action:** Executed mock tool and retrieved account data.

### Step 2 — Send Transactional Email (MEDIUM Risk)
- **Tool:** `send_email` (Risk: `MEDIUM`)
- **Parameters:** `{"to": "customer.9921@example.com", "subject": "Account Review", "body": "Your refund request is being processed."}`
- **Decision:** `ALLOW`
- **Request ID:** `5ab974c0-bb97-410c-8b36-6c4bee777ece`
- **Reason:** `All policy checks passed.`
- **Client Action:** Transactional email dispatched.

### Step 3 — Process High-Value Refund (HIGH Risk, Paused for HITL)
- **Tool:** `process_refund` (Risk: `HIGH`, Amount: `INR 75,000.0`)
- **Parameters:** `{"customer_id": "CUST-9921", "amount": 75000.0, "currency": "INR", "reason": "VIP billing adjustment"}`
- **Decision:** `PENDING`
- **Request ID:** `5cf226bd-4482-4c5a-80e7-d054ae32a821`
- **Reason:** `Action on tool 'process_refund' requires human approval (HITL).`
- **Client Action:** `AgentGuardPending` exception raised; agent execution paused awaiting human review.

### Step 4 — Human Manager Review & Approval
- **Manager Email:** `manager@agentguard-demo.local`
- **HITL Request ID:** `1ff210a7-d6c0-4e12-965f-07f1f965d40a`
- **Associated Tool Request ID:** `5cf226bd-4482-4c5a-80e7-d054ae32a821`
- **Review Note:** `"Approved VIP refund per customer agreement"`
- **Approval Decision:** `APPROVED`
- **Execution Payload:**
  ```json
  {
    "refund_id": "REF-F0F0AEFE",
    "amount": 75000.0,
    "customer_id": "CUST-9921",
    "reason": "VIP billing adjustment",
    "status": "completed",
    "processed_at": "2026-09-17T06:17:23.281141+00:00"
  }
  ```

### Step 5 — Destructive Database Deletion (CRITICAL Risk Override)
Two-phase demonstration proving the immutable safety gate:

#### 5A. Unpermitted Call
- **Tool:** `delete_database` (Risk: `CRITICAL`)
- **Permission Granted at Call Time:** `False`
- **Decision:** `DENY`
- **Request ID:** `d557dea4-c5bd-46cc-832c-bede32d1c635`
- **Reason:** `Agent 'FinanceAgent' has no permission grant for tool 'delete_database'.`

#### 5B. Explicitly Permitted Call (Override Verification)
- **Admin Action:** Executed `POST /api/v1/permissions` granting `is_allowed=True` to `FinanceAgent` for `delete_database` (`tool_id=45bce6bd-4a41-4b3c-8a1f-bff088f30190`).
- **Permission Granted at Call Time:** `True`
- **Decision:** `DENY`
- **Request ID:** `6561f8a1-cfae-48dc-8905-d5a057c267c8`
- **Reason:** `Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy.`
- **Result:** Security gate held. The policy engine's risk pipeline step safely overrode the explicit permission grant.

### Step 6 — Cryptographic Hash-Chain Verification
- **Auditor Email:** `auditor@agentguard-demo.local`
- **Endpoint:** `POST /api/v1/audit/verify`
- **Verification Result:** `VALID`
- **Records Verified:** `20` records in organization chain
- **Tampering Detected:** `0` (Zero broken hashes, zero sequence gaps)
- **Genesis Block Linkage:** `0000000000000000000000000000000000000000000000000000000000000000`

---

## Live Dashboard State Summary
Post-scenario snapshot from `GET /api/v1/dashboard/stats`:
- **Requests Today:** 10
- **Allowed Today:** 6
- **Blocked Today:** 1
- **Pending Today:** 2
