"""Demo 1: Custom Python Agent (No Framework).

Demonstrates governance of a custom OOP Python agent using the AgentGuard SDK.
No third-party agent framework is used — pure standard library Python.
"""
import sys
import os
from typing import Any, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agentguard import (
    AgentGuard,
    AgentGuardDenied,
    AgentGuardPending,
    AgentGuardError,
)
from demo.tools import mock_tools


class CustomSupportAgent:
    """Plain Python agent without external orchestration framework."""

    def __init__(self, guard_client: AgentGuard, agent_id: Optional[str] = None) -> None:
        self.client = guard_client
        self.agent_id = agent_id

    def handle_intent(self, tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Evaluate intent through AgentGuard and execute tool only if allowed."""
        print(f"\n[CustomAgent] Proposing action: {tool_name} with params={parameters}")
        try:
            result = self.client.guard(
                tool=tool_name,
                parameters=parameters,
                agent_id=self.agent_id,
            )
            print(f"[CustomAgent] -> ALLOWED by AgentGuard (request_id={result.request_id})")
            print(f"[CustomAgent] -> Reason: {result.reason}")

            # Client-side execution occurs only after ALLOW
            tool_fn = getattr(mock_tools, tool_name)
            tool_output = tool_fn(**parameters)
            print(f"[CustomAgent] -> Tool output: {tool_output}")
            return {
                "tool": tool_name,
                "decision": "ALLOW",
                "reason": result.reason,
                "request_id": result.request_id,
                "executed": True,
                "output": tool_output,
            }

        except AgentGuardDenied as exc:
            print(f"[CustomAgent] -> BLOCKED by AgentGuard (request_id={exc.request_id})")
            print(f"[CustomAgent] -> Reason: {exc.reason}")
            return {
                "tool": tool_name,
                "decision": "DENY",
                "reason": exc.reason,
                "request_id": exc.request_id,
                "executed": False,
                "output": None,
            }

        except AgentGuardPending as exc:
            print(f"[CustomAgent] -> PAUSED for Human Approval (request_id={exc.request_id})")
            print(f"[CustomAgent] -> Reason: {exc.reason}")
            return {
                "tool": tool_name,
                "decision": "PENDING",
                "reason": exc.reason,
                "request_id": exc.request_id,
                "executed": False,
                "output": None,
            }


def run_custom_agent(client: AgentGuard, agent_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Execute the standard suite of 3 tool intents: ALLOW, DENY, and PENDING."""
    print("=" * 60)
    print("DEMO 1: Custom Python Agent (No Framework)")
    print("=" * 60)
    agent = CustomSupportAgent(guard_client=client, agent_id=agent_id)

    intents = [
        ("read_customer", {"customer_id": "CUST-001"}),
        ("delete_database", {"database": "prod_users"}),
        ("process_refund", {"customer_id": "CUST-001", "amount": 1500.0, "reason": "damaged shipment"}),
    ]

    results = []
    for tool_name, params in intents:
        res = agent.handle_intent(tool_name, params)
        results.append(res)

    return results


if __name__ == "__main__":
    api_key = os.getenv("AGENTGUARD_API_KEY", "ag_live_demo")
    base_url = os.getenv("AGENTGUARD_BASE_URL", "http://localhost:8000/api/v1")
    agent_id = os.getenv("AGENTGUARD_AGENT_ID")
    client = AgentGuard(api_key=api_key, base_url=base_url)
    run_custom_agent(client, agent_id)
