# Python SDK Reference

`agentguard-sdk` is a lightweight Python package that routes an AI agent's tool calls through the AgentGuard Core Engine for governance evaluation.

The SDK never contains policy logic. It only calls the `POST /guard/check` API and translates the response into either a `GuardResult` (for ALLOW) or a structured exception (for DENY/PENDING).

---

## Installation

From the repository root:

```bash
cd sdk
pip install -e .
```

This installs `agentguard-sdk` version 0.1.0 in editable mode.

**Dependencies** (specified in `pyproject.toml`):
- `httpx >= 0.24.0`
- `pydantic >= 2.0.0`
- Python >= 3.9

---

## Quick Start

```python
from agentguard import AgentGuard, AgentGuardDenied, AgentGuardPending

# Initialize the client
client = AgentGuard(
    api_key="ag_live_...",                     # from POST /api/v1/auth/api-keys
    base_url="http://localhost:8000/api/v1",   # Core Engine URL
    agent_id="026ed85a-dab4-4773-aeb4-f027c0b73f80",  # agent UUID
)

# Evaluate a tool call
try:
    result = client.guard(
        tool="read_customer",
        parameters={"customer_id": "CUST-9921", "fields": ["name", "email"]},
    )
    if result.allowed:
        # Safe to execute the tool
        print(f"Permitted. Request ID: {result.request_id}")
except AgentGuardDenied as e:
    print(f"Blocked: {e.reason}")
except AgentGuardPending as e:
    print(f"Paused for human review: {e.reason}")
    # Agent should wait; poll HITL status using e.request_id

# Clean up
client.close()
```

The client also works as a context manager:

```python
with AgentGuard(api_key="ag_live_...", agent_id="...") as client:
    result = client.guard(tool="send_email", parameters={"to": "user@example.com"})
```

---

## Client API

### `AgentGuard(api_key, base_url, agent_id, timeout, max_retries, retry_backoff, http_client)`

Constructor. Creates a synchronous HTTP client for the Core Engine.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | *required* | API key (e.g., `"ag_live_..."`) |
| `base_url` | `str` | `"http://localhost:8000/api/v1"` | Core Engine base URL |
| `agent_id` | `str \| UUID \| None` | `None` | Default agent UUID for all calls |
| `timeout` | `float` | `5.0` | HTTP request timeout in seconds |
| `max_retries` | `int` | `1` | Network retry attempts (see Safe Retry) |
| `retry_backoff` | `float` | `0.2` | Base backoff delay in seconds (exponential) |
| `http_client` | `httpx.Client \| None` | `None` | Optional pre-configured httpx client |

### `client.guard(tool, parameters, *, action, agent_id, estimated_tokens, estimated_cost, metadata, timeout, max_retries, raise_for_status)`

Evaluate a proposed tool call through the AgentGuard policy engine.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool` | `str` | *required* | Tool name (e.g., `"read_customer"`) |
| `parameters` | `dict \| None` | `None` | Tool call parameters |
| `action` | `str` | `"execute"` | Action verb |
| `agent_id` | `str \| UUID \| None` | `None` | Override client-level agent_id |
| `estimated_tokens` | `int` | `0` | Estimated token usage for budget |
| `estimated_cost` | `float` | `0.0` | Estimated cost for budget caps |
| `metadata` | `dict \| None` | `None` | Custom context metadata |
| `timeout` | `float \| None` | `None` | Per-request timeout override |
| `max_retries` | `int \| None` | `None` | Per-request retry override |
| `raise_for_status` | `bool` | `True` | If True, DENY/PENDING raise exceptions |

**Returns:** `GuardResult` when `decision == "ALLOW"` (or when `raise_for_status=False`).

**Raises:**
- `AgentGuardDenied` — policy blocks the action (DENY)
- `AgentGuardPending` — action requires human review (PENDING)
- `AgentGuardAuthenticationError` — API key invalid or revoked (HTTP 401/403)
- `AgentGuardTimeout` — backend unreachable or timed out
- `AgentGuardServerError` — backend returned 5xx or unparseable response

### `client.close()`

Close the underlying HTTP client (if owned by this instance).

---

## Data Models

### `GuardResult`

Returned on successful evaluation (ALLOW, or any decision when `raise_for_status=False`).

| Field | Type | Description |
|-------|------|-------------|
| `allowed` | `bool` | `True` for ALLOW, `False` for DENY/PENDING |
| `decision` | `str` | `"ALLOW"`, `"DENY"`, or `"PENDING"` |
| `request_id` | `str \| None` | Server-assigned UUID for audit tracking |
| `reason` | `str` | Human-readable policy explanation |
| `raw_response` | `dict \| None` | Full JSON response from the backend |

### `GuardRequest`

Internal model for the `POST /guard/check` payload (you typically don't construct this directly):

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | `str \| UUID \| None` | Agent UUID |
| `tool_name` | `str` | Tool name (1–100 chars) |
| `action` | `str` | Action verb (default: `"execute"`) |
| `parameters` | `dict` | Tool call parameters |
| `estimated_tokens` | `int` | Token estimate (≥ 0) |
| `estimated_cost` | `float` | Cost estimate (≥ 0.0) |
| `metadata` | `dict \| None` | Custom metadata |

---

## Exception Hierarchy

All SDK exceptions inherit from `AgentGuardError`, so you can catch broadly or specifically:

```
AgentGuardError (base)
├── AgentGuardDenied          # Policy blocked the action
├── AgentGuardPending         # Queued for human review
├── AgentGuardAuthenticationError  # Invalid API key (401/403)
├── AgentGuardTimeout         # Network unreachable or timed out
└── AgentGuardServerError     # Backend 5xx or parse failure
```

### `AgentGuardDenied`

| Attribute | Type | Description |
|-----------|------|-------------|
| `reason` | `str` | Why the action was denied |
| `request_id` | `str \| None` | Audit trail reference |

### `AgentGuardPending`

| Attribute | Type | Description |
|-----------|------|-------------|
| `reason` | `str` | Why human review was required |
| `request_id` | `str \| None` | HITL request reference |

### `AgentGuardAuthenticationError`

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | `int` | HTTP status (401 or 403) |
| `detail` | `str \| None` | Backend error detail |

### `AgentGuardTimeout`

| Attribute | Type | Description |
|-----------|------|-------------|
| `message` | `str` | Description of the connection failure |

### `AgentGuardServerError`

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `detail` | `str \| None` | Backend error detail |
| `raw_response` | `str \| None` | Raw response body |

---

## Safe Retry Boundary

The SDK implements a **safe retry** policy to prevent dangerous double-execution:

1. **Retries ONLY on network-level failures** — `ConnectError`, `ConnectTimeout`, `NetworkError`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout` — where **no HTTP response was received from the server**.
2. **Never retries once the backend has responded** — if the server returned any HTTP response (200, 401, 500, etc.), the SDK processes it immediately and does **not** retry. This prevents duplicate budget deductions, duplicate audit entries, and double tool execution.
3. **Exponential backoff** — retry delay is `retry_backoff * (2 ** attempt)`.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Attempt 0 │────▶│   Attempt 1 │────▶│   Give up   │
│  Connect    │     │  200ms wait │     │  Raise      │
│  Error      │     │  Connect    │     │  Timeout    │
│             │     │  Error      │     │             │
└─────────────┘     └─────────────┘     └─────────────┘

But if any attempt gets an HTTP response:
┌─────────────┐     ┌─────────────┐
│   Attempt 0 │────▶│   Process   │     (NO retry)
│  HTTP 200   │     │   response  │
│  received   │     │             │
└─────────────┘     └─────────────┘
```

---

## Non-Raise Mode

By default, `client.guard()` raises `AgentGuardDenied` and `AgentGuardPending` as exceptions. If you prefer boolean branching:

```python
result = client.guard(
    tool="process_refund",
    parameters={"amount": 5000},
    raise_for_status=False,      # Don't raise on DENY/PENDING
)

if result.allowed:
    execute_tool()
elif result.decision == "PENDING":
    wait_for_approval(result.request_id)
elif result.decision == "DENY":
    log_denial(result.reason)
```

---

## Full Integration Example

```python
"""FinanceAgent using AgentGuard SDK for runtime governance."""
from agentguard import AgentGuard, AgentGuardDenied, AgentGuardPending

def run_finance_agent():
    with AgentGuard(
        api_key="ag_live_abc123...",
        base_url="http://localhost:8000/api/v1",
        agent_id="026ed85a-dab4-4773-aeb4-f027c0b73f80",
    ) as guard:

        # Step 1: Read customer (LOW risk → ALLOW)
        result = guard.guard(
            tool="read_customer",
            parameters={"customer_id": "CUST-9921", "fields": ["name", "email", "balance"]},
        )
        print(f"✓ Customer data retrieved (request_id={result.request_id})")

        # Step 2: Send email (MEDIUM risk → ALLOW)
        result = guard.guard(
            tool="send_email",
            parameters={"to": "customer@example.com", "subject": "Refund Status"},
        )
        print(f"✓ Email sent (request_id={result.request_id})")

        # Step 3: Process refund (HIGH risk → PENDING)
        try:
            guard.guard(
                tool="process_refund",
                parameters={"customer_id": "CUST-9921", "amount": 75000.0, "currency": "INR"},
                estimated_cost=75000.0,
            )
        except AgentGuardPending as e:
            print(f"⏸ Paused for human approval: {e.reason}")
            print(f"  Track via request_id: {e.request_id}")

        # Step 4: Attempt destructive action (CRITICAL risk → DENY)
        try:
            guard.guard(
                tool="delete_database",
                parameters={"target": "production"},
            )
        except AgentGuardDenied as e:
            print(f"✗ Blocked by policy: {e.reason}")

if __name__ == "__main__":
    run_finance_agent()
```
