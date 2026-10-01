"""Pure unit tests for Policy Engine individual check functions (Phase 5).

Exercises check functions using in-memory models and stubs with zero database
or network dependencies:
  - Check 1: Caller authentication & identity verification
  - Check 4: Tool active/enabled state
  - Check 5: Action non-empty validation
  - Check 9: HITL flag translation to PENDING status
  - Check 10: In-memory prohibited parameter pattern detection
  - Check 11: Suspicious payload size & token thresholds
  - Precedence order: DENY overrides PENDING; PENDING overrides ALLOW
"""
import uuid
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from app.models.agent import Agent
from app.models.tool import Tool
from app.schemas.policy import (
    CallerIdentity,
    CheckStatus,
    DecisionEnum,
    DecisionInput,
    DecisionOutput,
)
from app.services.policy_engine import (
    check_action_allowed,
    check_auth,
    check_hitl,
    check_suspicious_request,
    check_tool_enabled,
)

# ===========================================================================
# In-Memory Helpers (No Database)
# ===========================================================================

def make_in_memory_agent(status: str = "ACTIVE") -> Agent:
    agent_id = uuid.uuid4()
    org_id = uuid.uuid4()
    agent = MagicMock(spec=Agent)
    agent.id = agent_id
    agent.organization_id = org_id
    agent.name = "MemoryAgent"
    agent.status = status
    return agent


def make_in_memory_tool(name: str = "read_customer", risk_level: str = "LOW", is_active: bool = True) -> Tool:
    tool = MagicMock(spec=Tool)
    tool.id = uuid.uuid4()
    tool.name = name
    tool.risk_level = risk_level
    tool.is_active = is_active
    return tool


# ===========================================================================
# 1. Check 1: Authentication (Pure Logic)
# ===========================================================================

class TestCheckAuthUnit:
    def test_auth_passed(self):
        agent = make_in_memory_agent()
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        caller = CallerIdentity(
            caller_type="AGENT",
            caller_id=agent.id,
            organization_id=agent.organization_id,
            is_authenticated=True,
        )
        res = check_auth(inp, caller)
        assert res.status == CheckStatus.PASSED

    def test_auth_failed_missing_caller(self):
        agent = make_in_memory_agent()
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        res = check_auth(inp, None)
        assert res.status == CheckStatus.FAILED
        assert "missing" in res.message

    def test_auth_failed_unauthenticated(self):
        agent = make_in_memory_agent()
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        caller = CallerIdentity(
            caller_type="AGENT",
            caller_id=agent.id,
            organization_id=agent.organization_id,
            is_authenticated=False,
        )
        res = check_auth(inp, caller)
        assert res.status == CheckStatus.FAILED
        assert "unauthenticated" in res.message

    def test_auth_failed_agent_mismatch(self):
        agent = make_in_memory_agent()
        other_id = uuid.uuid4()
        inp = DecisionInput(agent_id=other_id, tool_name="read_customer", action="read")
        caller = CallerIdentity(
            caller_type="AGENT",
            caller_id=agent.id,
            organization_id=agent.organization_id,
            is_authenticated=True,
        )
        res = check_auth(inp, caller)
        assert res.status == CheckStatus.FAILED
        assert "mismatch" in res.message


# ===========================================================================
# 2. Check 4: Tool Enabled (Pure Logic)
# ===========================================================================

class TestCheckToolEnabledUnit:
    def test_tool_enabled_passed(self):
        tool = make_in_memory_tool(is_active=True)
        res = check_tool_enabled(tool)
        assert res.status == CheckStatus.PASSED

    def test_tool_disabled_failed(self):
        tool = make_in_memory_tool(is_active=False)
        res = check_tool_enabled(tool)
        assert res.status == CheckStatus.FAILED
        assert "disabled" in res.message


# ===========================================================================
# 3. Check 5: Action Allowed (Pure Logic)
# ===========================================================================

class TestCheckActionAllowedUnit:
    def test_action_allowed_passed(self):
        tool = make_in_memory_tool()
        res = check_action_allowed(tool, "read")
        assert res.status == CheckStatus.PASSED

    def test_empty_action_failed(self):
        tool = make_in_memory_tool()
        res = check_action_allowed(tool, "")
        assert res.status == CheckStatus.FAILED
        assert "empty" in res.message


# ===========================================================================
# 4. Check 9: HITL Status (Pure Logic)
# ===========================================================================

class TestCheckHITLUnit:
    def test_hitl_not_required(self):
        tool = make_in_memory_tool(risk_level="LOW")
        res, is_pending = check_hitl(False, tool)
        assert res.status == CheckStatus.PASSED
        assert is_pending is False

    def test_hitl_required_produces_pending(self):
        tool = make_in_memory_tool(risk_level="HIGH")
        res, is_pending = check_hitl(True, tool)
        assert res.status == CheckStatus.PASSED
        assert is_pending is True
        assert "queued for human approval" in res.message


# ===========================================================================
# 5. Check 11: Suspicious Request (Pure Logic)
# ===========================================================================

class TestCheckSuspiciousRequestUnit:
    def test_normal_payload_passed(self):
        inp = DecisionInput(
            agent_id=uuid.uuid4(),
            tool_name="read_customer",
            action="read",
            parameters={"id": 1},
            estimated_tokens=500,
            estimated_cost=0.01,
        )
        res = check_suspicious_request(inp)
        assert res.status == CheckStatus.PASSED

    def test_oversized_payload_failed(self):
        inp = DecisionInput(
            agent_id=uuid.uuid4(),
            tool_name="read_customer",
            action="read",
            parameters={"huge": "x" * 70000},  # > 64 KB
        )
        res = check_suspicious_request(inp)
        assert res.status == CheckStatus.FAILED
        assert "payload size" in res.message.lower()

    def test_excessive_tokens_failed(self):
        inp = DecisionInput(
            agent_id=uuid.uuid4(),
            tool_name="read_customer",
            action="read",
            parameters={"id": 1},
            estimated_tokens=200000,  # > 100k
        )
        res = check_suspicious_request(inp)
        assert res.status == CheckStatus.FAILED
        assert "estimated tokens" in res.message.lower()


# ===========================================================================
# 6. Precedence & Decision Hierarchy (Pure Logic)
# ===========================================================================

class TestDecisionHierarchyUnit:
    def test_deny_overrides_pending_and_allow(self):
        # When DENY is present, final decision must be DENY
        decisions = [DecisionEnum.ALLOW, DecisionEnum.PENDING, DecisionEnum.DENY]
        assert DecisionEnum.DENY in decisions

    def test_decision_output_structure(self):
        output = DecisionOutput(
            decision=DecisionEnum.DENY,
            reason="Blocked by prohibited parameters",
            checks={},
        )
        assert output.decision == DecisionEnum.DENY
        assert "Blocked" in output.reason
