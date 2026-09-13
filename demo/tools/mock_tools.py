"""Shared agent-side mock tools for the AgentGuard Phase 11 demos.

These represent the client-side tool execution logic that an agent would execute
ONLY AFTER AgentGuard returns an ALLOW decision.
"""
from typing import Any


def read_customer(customer_id: str) -> dict[str, Any]:
    """Client-side tool execution for reading customer profile."""
    return {
        "status": "success",
        "customer_id": customer_id,
        "name": "Jane Doe",
        "email": "jane.doe@example.com",
        "tier": "enterprise",
    }


def process_refund(customer_id: str, amount: float, reason: str = "Customer requested") -> dict[str, Any]:
    """Client-side tool execution for processing a customer refund."""
    return {
        "status": "success",
        "customer_id": customer_id,
        "amount": amount,
        "reason": reason,
        "transaction_status": "refund_submitted",
    }


def delete_database(database: str) -> dict[str, Any]:
    """Destructive client-side tool execution (should NEVER be reached if guarded)."""
    return {
        "status": "executed",
        "database": database,
        "warning": "Database records purged",
    }
