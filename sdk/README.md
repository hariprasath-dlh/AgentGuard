# agentguard-sdk

Developer SDK for the AgentGuard runtime governance layer.

## Installation

```bash
pip install agentguard-sdk
```

## Quickstart

```python
from agentguard import AgentGuard, AgentGuardDenied, AgentGuardPending

client = AgentGuard(
    api_key="ag_live_...",
    base_url="http://localhost:8000/api/v1",
)

try:
    result = client.guard(
        tool="read_customer",
        parameters={"customer_id": "CUST-1001"},
    )
    if result.allowed:
        print("Action allowed:", result.request_id)
except AgentGuardDenied as e:
    print(f"Action blocked by policy: {e.reason}")
except AgentGuardPending as e:
    print(f"Action paused for human review: {e.reason} (req_id: {e.request_id})")
```
