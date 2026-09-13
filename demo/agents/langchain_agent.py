"""Demo 2: LangChain-Style Tool Agent.

Demonstrates AgentGuard governance using LangChain interface conventions:
- Tools defined with name, description, and callable functions.
- An AgentExecutor-style tool dispatch loop.
- Interception layer wrapping tool execution with client.guard(...).

NOTE: We use a lightweight, faithful implementation of LangChain's tool-dispatch
contract to avoid heavy external dependencies while proving seamless integration
with LangChain agent architectures.
"""
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agentguard import (
    AgentGuard,
    AgentGuardDenied,
    AgentGuardPending,
)
from demo.tools import mock_tools


@dataclass
class LangChainTool:
    """Tool specification matching LangChain's BaseTool / StructuredTool interface."""
    name: str
    description: str
    func: Callable[..., Any]

    def run(self, **kwargs) -> Any:
        return self.func(**kwargs)


class LangChainAgentExecutor:
    """Simulates a LangChain AgentExecutor with AgentGuard pre-dispatch governance."""

    def __init__(
        self,
        tools: list[LangChainTool],
        guard_client: AgentGuard,
        agent_id: Optional[str] = None,
    ) -> None:
        self.tools = {tool.name: tool for tool in tools}
        self.guard = guard_client
        self.agent_id = agent_id

    def execute_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Intercept and evaluate the proposed tool call before executing."""
        print(f"\n[LangChainAgent] Tool call requested: {tool_name}({tool_input})")
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in registered tools.")

        tool = self.tools[tool_name]

        # PRE-DISPATCH GATEWAY CALL:
        try:
            decision = self.guard.guard(
                tool=tool_name,
                parameters=tool_input,
                agent_id=self.agent_id,
            )
            print(f"[LangChainAgent] -> AgentGuard: ALLOW (request_id={decision.request_id})")
            print(f"[LangChainAgent] -> Reason: {decision.reason}")

            # Execution occurs only upon ALLOW
            observation = tool.run(**tool_input)
            print(f"[LangChainAgent] -> Observation: {observation}")
            return {
                "tool": tool_name,
                "decision": "ALLOW",
                "reason": decision.reason,
                "request_id": decision.request_id,
                "executed": True,
                "output": observation,
            }

        except AgentGuardDenied as exc:
            print(f"[LangChainAgent] -> AgentGuard: DENIED (request_id={exc.request_id})")
            print(f"[LangChainAgent] -> Reason: {exc.reason}")
            return {
                "tool": tool_name,
                "decision": "DENY",
                "reason": exc.reason,
                "request_id": exc.request_id,
                "executed": False,
                "output": None,
            }

        except AgentGuardPending as exc:
            print(f"[LangChainAgent] -> AgentGuard: PENDING HITL (request_id={exc.request_id})")
            print(f"[LangChainAgent] -> Reason: {exc.reason}")
            return {
                "tool": tool_name,
                "decision": "PENDING",
                "reason": exc.reason,
                "request_id": exc.request_id,
                "executed": False,
                "output": None,
            }


def run_langchain_agent(client: AgentGuard, agent_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Execute the standard suite of 3 tool calls through the LangChain-style agent."""
    print("=" * 60)
    print("DEMO 2: LangChain-Style Tool Agent")
    print("=" * 60)

    # Register LangChain tools
    tools = [
        LangChainTool(
            name="read_customer",
            description="Look up customer profile information",
            func=mock_tools.read_customer,
        ),
        LangChainTool(
            name="delete_database",
            description="Permanently delete database records",
            func=mock_tools.delete_database,
        ),
        LangChainTool(
            name="process_refund",
            description="Issue a monetary refund to a customer",
            func=mock_tools.process_refund,
        ),
    ]

    executor = LangChainAgentExecutor(tools=tools, guard_client=client, agent_id=agent_id)

    plan = [
        ("read_customer", {"customer_id": "CUST-001"}),
        ("delete_database", {"database": "prod_users"}),
        ("process_refund", {"customer_id": "CUST-001", "amount": 1500.0, "reason": "damaged shipment"}),
    ]

    results = []
    for tool_name, tool_input in plan:
        res = executor.execute_tool_call(tool_name, tool_input)
        results.append(res)

    return results


if __name__ == "__main__":
    api_key = os.getenv("AGENTGUARD_API_KEY", "ag_live_demo")
    base_url = os.getenv("AGENTGUARD_BASE_URL", "http://localhost:8000/api/v1")
    agent_id = os.getenv("AGENTGUARD_AGENT_ID")
    client = AgentGuard(api_key=api_key, base_url=base_url)
    run_langchain_agent(client, agent_id)
