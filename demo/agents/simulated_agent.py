"""Demo 3: Simulated Agent (Event-Driven State Machine).

Demonstrates AgentGuard governance in an intent-driven finite state machine (FSM).
This represents a custom orchestration engine with no framework concepts at all —
proving that AgentGuard enforces governance over plain JSON/HTTP without assuming
any framework's execution model or architecture.
"""
import sys
import os
from enum import Enum
from typing import Any, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agentguard import (
    AgentGuard,
    AgentGuardDenied,
    AgentGuardPending,
)
from demo.tools import mock_tools


class AgentState(str, Enum):
    IDLE = "IDLE"
    PROPOSING = "PROPOSING"
    GOVERNANCE_EVALUATION = "GOVERNANCE_EVALUATION"
    EXECUTING = "EXECUTING"
    PAUSED_HITL = "PAUSED_HITL"
    BLOCKED = "BLOCKED"


class SimulatedStateMachineAgent:
    """State-machine agent with event-driven state transitions."""

    def __init__(self, guard: AgentGuard, agent_id: Optional[str] = None) -> None:
        self.guard = guard
        self.agent_id = agent_id
        self.state = AgentState.IDLE

    def step(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Process an intent through state machine transitions."""
        tool_name = intent["tool"]
        parameters = intent["parameters"]

        self.state = AgentState.PROPOSING
        print(f"\n[SimulatedAgent] State={self.state.value} | Intent={tool_name} params={parameters}")

        self.state = AgentState.GOVERNANCE_EVALUATION
        print(f"[SimulatedAgent] State={self.state.value} | Consulting AgentGuard...")

        try:
            decision = self.guard.guard(
                tool=tool_name,
                parameters=parameters,
                agent_id=self.agent_id,
            )
            # ALLOW branch
            self.state = AgentState.EXECUTING
            print(f"[SimulatedAgent] State={self.state.value} | Action ALLOWED (request_id={decision.request_id})")
            print(f"[SimulatedAgent] -> Reason: {decision.reason}")

            tool_func = getattr(mock_tools, tool_name)
            output = tool_func(**parameters)
            print(f"[SimulatedAgent] -> Execution result: {output}")

            self.state = AgentState.IDLE
            return {
                "tool": tool_name,
                "decision": "ALLOW",
                "reason": decision.reason,
                "request_id": decision.request_id,
                "executed": True,
                "output": output,
                "final_state": self.state.value,
            }

        except AgentGuardDenied as exc:
            self.state = AgentState.BLOCKED
            print(f"[SimulatedAgent] State={self.state.value} | Action DENIED (request_id={exc.request_id})")
            print(f"[SimulatedAgent] -> Reason: {exc.reason}")
            return {
                "tool": tool_name,
                "decision": "DENY",
                "reason": exc.reason,
                "request_id": exc.request_id,
                "executed": False,
                "output": None,
                "final_state": self.state.value,
            }

        except AgentGuardPending as exc:
            self.state = AgentState.PAUSED_HITL
            print(f"[SimulatedAgent] State={self.state.value} | Action PAUSED for HITL (request_id={exc.request_id})")
            print(f"[SimulatedAgent] -> Reason: {exc.reason}")
            return {
                "tool": tool_name,
                "decision": "PENDING",
                "reason": exc.reason,
                "request_id": exc.request_id,
                "executed": False,
                "output": None,
                "final_state": self.state.value,
            }


def run_simulated_agent(client: AgentGuard, agent_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Execute the standard suite of 3 tool intents through the state machine agent."""
    print("=" * 60)
    print("DEMO 3: Simulated Agent (Event-Driven State Machine)")
    print("=" * 60)

    agent = SimulatedStateMachineAgent(guard=client, agent_id=agent_id)

    queue = [
        {"tool": "read_customer", "parameters": {"customer_id": "CUST-001"}},
        {"tool": "delete_database", "parameters": {"database": "prod_users"}},
        {"tool": "process_refund", "parameters": {"customer_id": "CUST-001", "amount": 1500.0, "reason": "damaged shipment"}},
    ]

    results = []
    for item in queue:
        res = agent.step(item)
        results.append(res)

    return results


if __name__ == "__main__":
    api_key = os.getenv("AGENTGUARD_API_KEY", "ag_live_demo")
    base_url = os.getenv("AGENTGUARD_BASE_URL", "http://localhost:8000/api/v1")
    agent_id = os.getenv("AGENTGUARD_AGENT_ID")
    client = AgentGuard(api_key=api_key, base_url=base_url)
    run_simulated_agent(client, agent_id)
