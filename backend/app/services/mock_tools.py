"""Mock tool handlers for AgentGuard Phase 7.

Safe, deterministic fake handlers for demo tools that return plausible
results and do nothing destructive.

INTENTIONALLY EXCLUDED:
- process_refund: Only executes after HITL approval (Phase 9).
- delete_database: Never executes in this project. If the policy engine
  ever returns ALLOW for delete_database, that is a bug.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional


def read_customer(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return a fake customer profile."""
    customer_id = parameters.get("customer_id", "CUST-0001")
    return {
        "customer_id": customer_id,
        "name": "Jane Doe",
        "email": "jane.doe@example.com",
        "account_status": "active",
        "plan": "enterprise",
        "created_at": "2024-01-15T10:30:00Z",
    }


def create_ticket(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return a fake support ticket confirmation."""
    return {
        "ticket_id": f"TKT-{uuid.uuid4().hex[:8].upper()}",
        "subject": parameters.get("subject", "Support request"),
        "priority": parameters.get("priority", "normal"),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def send_email(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return a fake email-sent confirmation."""
    return {
        "message_id": f"MSG-{uuid.uuid4().hex[:8].upper()}",
        "to": parameters.get("to", "customer@example.com"),
        "subject": parameters.get("subject", "Notification"),
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


def process_refund(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return a fake refund confirmation for Phase 9 HITL approval demo."""
    return {
        "refund_id": f"REF-{uuid.uuid4().hex[:8].upper()}",
        "amount": parameters.get("amount", 0.0),
        "customer_id": parameters.get("customer_id", "CUST-0001"),
        "reason": parameters.get("reason", "Customer requested refund"),
        "status": "completed",
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Handler registry — the gateway looks up by tool name.
# Absence means no execution (safe fallback).
# ---------------------------------------------------------------------------
def get_handler(tool_name: str) -> Optional[Callable[[dict[str, Any]], dict[str, Any]]]:
    """Look up a mock handler by tool name. Returns None if no handler exists."""
    if tool_name in ("read_customer", "create_ticket", "send_email", "process_refund"):
        handler = globals().get(tool_name)
        if callable(handler):
            return handler
    return None

