# agentguard-sdk

Official Python Developer SDK for the **AgentGuard** runtime governance and policy enforcement layer.

AgentGuard intercepts proposed AI agent tool calls before dispatch, evaluates them against organizational RBAC, risk policies, token/rate limits, and cost budgets, and logs decisions to a cryptographic tamper-evident audit vault.

---

## Installation

```bash
pip install agentguard-sdk
```

**Requirements:** Python 3.9+ with `httpx` and `pydantic`.

---

## Core Usage

### Standard Exception-Driven Pattern

By default, `client.guard(...)` returns a `GuardResult` on `ALLOW`, and raises structured exceptions when an action is blocked or queued for approval:

```python
from agentguard import (
    AgentGuard,
    AgentGuardDenied,
    AgentGuardPending,
    AgentGuardAuthenticationError,
    AgentGuardTimeout,
    AgentGuardServerError,
)

# Initialize client
client = AgentGuard(
    api_key="ag_agent_your_key_here",
    base_url="http://localhost:8000/api/v1",  # Core Engine Gateway URL
)

try:
    result = client.guard(
        tool="read_customer",
        parameters={"customer_id": "CUST-1001"},
        estimated_tokens=50,
        estimated_cost=0.001,
    )
    if result.allowed:
        print(f"Action allowed! Request ID: {result.request_id}")
        # Safely execute the real tool call here

except AgentGuardDenied as e:
    # Action was rejected by policy (e.g. CRITICAL risk, unpermitted tool, rate/budget exceeded)
    print(f"Action DENIED: {e.reason} (request_id={e.request_id})")

except AgentGuardPending as e:
    # Action requires human-in-the-loop (HITL) approval
    print(f"Action paused for human approval: {e.reason} (request_id={e.request_id})")

except AgentGuardAuthenticationError as e:
    print(f"Authentication failed (HTTP {e.status_code}): {e.detail}")

except AgentGuardTimeout as e:
    print(f"Connection to AgentGuard timed out or was refused: {e}")

except AgentGuardServerError as e:
    print(f"AgentGuard backend error (HTTP {e.status_code}): {e.detail}")

finally:
    client.close()
```

---

### Context Manager Support

`AgentGuard` instances can be managed automatically via a `with` block:

```python
from agentguard import AgentGuard

with AgentGuard(api_key="ag_agent_...") as client:
    result = client.guard(tool="send_email", parameters={"to": "user@example.com"})
    print("Allowed:", result.allowed)
```

---

### Non-Raising / Boolean Return Mode

Pass `raise_for_status=False` to inspect decisions via the returned `GuardResult` without catching exceptions:

```python
with AgentGuard(api_key="ag_agent_...") as client:
    result = client.guard(
        tool="process_refund",
        parameters={"amount": 5000},
        raise_for_status=False,
    )

    if result.allowed:
        print("Proceeding with refund...")
    elif result.decision == "PENDING":
        print(f"Queued for human review. Request ID: {result.request_id}")
    elif result.decision == "DENY":
        print(f"Refund denied: {result.reason}")
```

---

## API Reference

### `AgentGuard` Constructor

```python
AgentGuard(
    api_key: str,
    base_url: str = "http://localhost:8000/api/v1",
    agent_id: Optional[Union[uuid.UUID, str]] = None,
    timeout: float = 5.0,
    max_retries: int = 1,
    retry_backoff: float = 0.2,
    http_client: Optional[httpx.Client] = None,
)
```

### `client.guard(...)` Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tool` | `str` | *required* | Name of the tool to be executed (e.g. `"read_customer"`). |
| `parameters` | `dict` | `{}` | Key-value dictionary of arguments for the tool. |
| `action` | `str` | `"execute"` | Action verb associated with the tool call. |
| `agent_id` | `UUID \| str` | `None` | Optional override for the requesting agent UUID. |
| `estimated_tokens` | `int` | `0` | Estimated token usage for sliding-window token rate limiting. |
| `estimated_cost` | `float` | `0.0` | Estimated monetary spend for budget enforcement. |
| `metadata` | `dict` | `None` | Custom context or telemetry dictionary attached to audit log. |
| `timeout` | `float` | `None` | Per-request timeout override in seconds. |
| `max_retries` | `int` | `None` | Per-request network retry attempts (safe network failures only). |
| `raise_for_status` | `bool` | `True` | If `True`, raises `AgentGuardDenied` or `AgentGuardPending`. If `False`, returns `GuardResult` with `.allowed=False`. |

### `GuardResult` Object Attributes

- `allowed` (`bool`): `True` if permitted, `False` otherwise.
- `decision` (`str`): `"ALLOW"`, `"DENY"`, or `"PENDING"`.
- `request_id` (`str`): Server-generated UUID uniquely tracking this evaluation in the audit vault.
- `reason` (`str`): Human-readable explanation of policy decision.
- `raw_response` (`dict`): Raw JSON response dictionary from the gateway.

### Exception Hierarchy

```
AgentGuardError (Base Exception)
├── AgentGuardDenied (Action blocked by policy)
│   ├── reason: str
│   └── request_id: Optional[str]
├── AgentGuardPending (Action paused for human approval)
│   ├── reason: str
│   └── request_id: Optional[str]
├── AgentGuardAuthenticationError (HTTP 401/403)
│   ├── status_code: int
│   └── detail: Optional[str]
├── AgentGuardTimeout (Unreachable / network dropped)
│   └── message: str
└── AgentGuardServerError (HTTP 5xx / unexpected response)
    ├── status_code: int
    ├── detail: Optional[str]
    └── raw_response: Optional[str]
```

