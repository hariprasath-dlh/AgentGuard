# Human-in-the-Loop (HITL)

This document describes AgentGuard's Human-in-the-Loop system, which pauses HIGH-risk agent actions for asynchronous human review before allowing execution.

---

## Purpose

When an agent proposes a tool call rated HIGH risk, the governance pipeline does not make the decision autonomously. Instead, it:

1. Returns `PENDING` to the agent (which pauses the agent)
2. Creates a `hitl_requests` record in the database
3. Waits for a human reviewer (MANAGER or ADMIN role) to approve or deny the request via the Control Plane
4. Executes the mock tool handler only after an explicit approval is committed to the database

---

## Lifecycle States

A HITL request moves through exactly this state machine:

```
                    ┌──────────────────────────────────────────────┐
                    │                                              │
 guard/check        │                                              ▼
 returns PENDING ──▶│  PENDING ──[approve]──▶ APPROVED ──▶ (tool executes)
                    │     │
                    │     ├──[deny]──▶ DENIED
                    │     │
                    │     └──[expires_at reached]──▶ EXPIRED
                    │
                    └──────────────────────────────────────────────┘
```

| State | Meaning |
|-------|---------|
| `PENDING` | Awaiting human review. Tool has not executed. |
| `APPROVED` | Reviewer approved. Tool mock handler has been called (or skipped if no handler exists). |
| `DENIED` | Reviewer denied. Tool will not execute. |
| `EXPIRED` | The 24-hour expiration window passed before a human reviewed it. |

Once a request reaches APPROVED, DENIED, or EXPIRED, it cannot transition to any other state. Attempting to approve or deny an already-resolved request returns HTTP 400.

---

## Creation

A `hitl_requests` record is created automatically by the Guard Gateway (`POST /api/v1/guard/check`) when:

- The policy engine returns `PENDING` (i.e., the tool's risk level is HIGH and the organization's RISK policy maps HIGH → HITL)

The request is created with:
- `status = "PENDING"`
- `expires_at = now + 24 hours` (UTC)
- A link to the corresponding `tool_requests` record

The gateway commits this record to the database **before** returning the PENDING response to the agent, ensuring that if the response is lost in transit, the HITL request still exists.

---

## Expiration Mechanism

Expiration uses a **lazy + sweep** dual approach rather than a background job:

### Lazy Expiration (On Access)

When a reviewer fetches a single HITL request via `GET /hitl/{id}`, or when `approve`/`deny` is called, the system checks the current time against `expires_at`:

```python
def _check_lazy_expiration(db, hitl):
    if hitl.status == "PENDING" and hitl.expires_at is not None:
        now = datetime.now(timezone.utc)
        if now >= expires_at:
            hitl.status = "EXPIRED"
            db.commit()
            return True
    return hitl.status == "EXPIRED"
```

If the request is found to be expired, it is immediately transitioned to EXPIRED and the approve/deny action is rejected with HTTP 400.

### Sweep Expiration (On List)

When a reviewer calls `GET /hitl` (the list endpoint), the system runs a sweep across all PENDING requests for the organization that have passed their `expires_at`:

```python
def sweep_expired_hitl_requests(db, organization_id=None):
    now = datetime.now(timezone.utc)
    query = db.query(HITLRequest).filter(
        HITLRequest.status == "PENDING",
        HITLRequest.expires_at.isnot(None),
        HITLRequest.expires_at <= now,
    )
    # ... filter by org, bulk-update to EXPIRED, commit
```

This sweep runs automatically at the start of every `GET /hitl` call, ensuring the list view is always current without requiring a periodic background job.

**Known limitation:** There is no scheduled background job running independently of API calls. If no user calls `GET /hitl` for an extended period, PENDING requests won't be transitioned to EXPIRED in the database until someone makes an API call. This is a lazy-evaluation tradeoff — acceptable for AgentGuard's current usage pattern.

---

## Approval Flow (Commit-Before-Execute)

The approval process follows a strict ordering to ensure audit integrity:

```
POST /hitl/{id}/approve
        │
        ▼
1. Load HITLRequest + linked ToolRequest
        │
        ▼
2. Check lazy expiration — reject if EXPIRED
        │
        ▼
3. Check status == "PENDING" — reject if already resolved
        │
        ▼
4. Update HITLRequest to APPROVED
   Update ToolRequest.decision to APPROVED
   Write HITL_APPROVED audit log entry
        │
        ▼
5. ── COMMIT ── (HARD GATE)
   If commit fails: return HTTP 500, handler NEVER called
        │
        ▼
6. Look up mock tool handler by tool name
        │
        ├── handler found ──▶ Execute mock handler
        │                          │
        │                    success ──▶ Write TOOL_EXECUTED audit entry
        │                    error   ──▶ Write TOOL_EXECUTION_FAILED audit entry
        │
        └── no handler ──▶ Write TOOL_EXECUTION_SKIPPED audit entry
        │
        ▼
7. COMMIT (execution audit entries)
        │
        ▼
8. Return enriched HITLRequestResponse
```

### Why Commit-Before-Execute?

The approval decision is committed durably before the mock tool handler runs. This guarantees:

- If the mock handler raises an exception, the approval is still in the database. The error is recorded in `output_payload` and a `TOOL_EXECUTION_FAILED` audit entry is written, but the approval is not reverted.
- If the process crashes between commit and execution, the approval is durable. The tool handler's output is simply absent — there's no inconsistency.
- Double-approval is impossible — the status check at step 3 prevents approving an already-APPROVED request.

---

## Denial Flow

Denial is simpler than approval — no tool handler is executed:

```
POST /hitl/{id}/deny
        │
        ▼
1. Check expiration and PENDING status (same as approval)
        │
        ▼
2. Update HITLRequest to DENIED
   Update ToolRequest.decision to DENIED
   Write HITL_DENIED audit log entry
        │
        ▼
3. COMMIT
        │
        ▼
4. Return enriched HITLRequestResponse
```

---

## What Happens When the Mock Handler Fails

If the approved mock handler raises an exception during resume:

1. The error is caught — the approve endpoint does **not** return HTTP 500
2. `execution_output = {"execution_status": "error", "error": str(exc)}` is stored in `tool_request.output_payload`
3. A `TOOL_EXECUTION_FAILED` audit entry is written with `decision = "ERROR"`
4. The `HITLRequest.status` remains `APPROVED` — the human's decision is not reverted
5. The HTTP response returns successfully with the enriched HITL request showing the error output

In other words: the human's approval decision is treated as final. A technical failure in mock execution is recorded but does not undo the governance decision.

---

## HITL Request Schema

The `HITLRequest` response object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | HITL request ID |
| `organization_id` | UUID | Organization scope |
| `tool_request_id` | UUID | Linked tool request |
| `status` | string | PENDING, APPROVED, DENIED, EXPIRED |
| `reviewer_id` | UUID or null | UUID of reviewing user |
| `review_notes` | string or null | Optional notes from reviewer |
| `expires_at` | datetime | 24 hours after creation |
| `reviewed_at` | datetime or null | When approval/denial was recorded |
| `created_at` | datetime | When the HITL request was created |
| `tool_name` | string or null | Name of the tool being evaluated |
| `agent_id` | UUID or null | Agent that proposed the tool call |
| `input_payload` | dict or null | Parameters passed to the tool |
| `output_payload` | dict or null | Handler result or error |

---

## Agent Behavior

The SDK translates a PENDING decision into `AgentGuardPending`:

```python
try:
    result = client.guard(tool="process_refund", parameters={...})
except AgentGuardPending as e:
    # e.reason: "Action on tool 'process_refund' requires human approval (HITL)."
    # e.request_id: UUID to track approval status
    print(f"Paused. Request: {e.request_id}")
    # Agent should pause execution and optionally poll for approval
```

AgentGuard does not implement a callback or webhook mechanism to resume the agent automatically. The agent is responsible for polling the HITL status endpoint or waiting for an out-of-band notification. When the request is APPROVED, the agent can re-issue the `guard/check` call — but note that the tool will not execute a second time via the guard endpoint; re-submission creates a new request. In the current demo design, the mock tool handler is executed server-side during the HITL approval flow.

---

## API Endpoints

See [api.md](api.md#hitl-human-in-the-loop) for the full HITL endpoint reference.

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| `GET` | `/hitl` | ADMIN, MANAGER | List all HITL requests (runs sweep expiration) |
| `GET` | `/hitl/{id}` | ADMIN, MANAGER | Get one (runs lazy expiration) |
| `POST` | `/hitl/{id}/approve` | ADMIN, MANAGER | Approve and execute |
| `POST` | `/hitl/{id}/deny` | ADMIN, MANAGER | Deny without executing |
