"""Unit and Integration Tests for AgentGuard Policy Engine (Phase 5).

Verifies:
  - Isolated testing for all 11 checks (both PASS and FAIL / PENDING branches)
  - Full pipeline evaluation and short-circuiting
  - Precedence order: DENY > PENDING > ALLOW
  - Table-driven risk rules and parameter denylists via policies table
  - Explicit test cases required by project.md:
      1. CRITICAL-risk tool always denied regardless of permissions.
      2. HIGH-risk tool with permission produces PENDING, not ALLOW.
      3. LOW-risk tool with permission produces ALLOW with no human step.
      4. Unpermitted agent denied before risk level evaluated (TOOL PERMISSION before RISK LEVEL).
      5. DENY from PROHIBITED PARAMETERS overrides PENDING from HITL.
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.policy import Policy
from app.models.tool import Tool
from app.repositories.registry import AgentRepository, PermissionRepository, ToolRepository
from app.schemas.policy import (
    CallerIdentity,
    CheckResult,
    CheckStatus,
    DecisionEnum,
    DecisionInput,
    DecisionOutput,
)
from app.services.policy_engine import (
    PolicyEngine,
    check_action_allowed,
    check_agent_status,
    check_auth,
    check_budget,
    check_hitl,
    check_prohibited_parameters,
    check_rate_limit,
    check_risk_level,
    check_suspicious_request,
    check_tool_enabled,
    check_tool_permission,
    default_budget_checker,
    default_rate_limit_checker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org_and_agent(db_session: Session):
    """Creates a test organization and an active agent."""
    org = Organization(name="Policy Test Org", slug=f"policy-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    agent = Agent(
        organization_id=org.id,
        name="FinanceAgent",
        description="Handles finance operations",
        status="ACTIVE",
    )
    db_session.add(agent)
    db_session.flush()
    return org, agent


@pytest.fixture
def tools_fixture(db_session: Session, org_and_agent):
    """Creates tools with various risk levels and sets up permissions."""
    org, agent = org_and_agent

    tool_low = Tool(organization_id=org.id, name="read_customer", risk_level="LOW", is_active=True)
    tool_med = Tool(organization_id=org.id, name="send_email", risk_level="MEDIUM", is_active=True)
    tool_high = Tool(organization_id=org.id, name="process_refund", risk_level="HIGH", is_active=True)
    tool_crit = Tool(organization_id=org.id, name="delete_database", risk_level="CRITICAL", is_active=True)
    tool_disabled = Tool(organization_id=org.id, name="disabled_tool", risk_level="LOW", is_active=False)

    for t in [tool_low, tool_med, tool_high, tool_crit, tool_disabled]:
        db_session.add(t)
    db_session.flush()

    # Grant permissions to agent for read_customer, process_refund, and delete_database
    for t in [tool_low, tool_high, tool_crit]:
        perm = AgentToolPermission(
            organization_id=org.id,
            agent_id=agent.id,
            tool_id=t.id,
            is_allowed=True,
        )
        db_session.add(perm)

    db_session.flush()
    return {
        "low": tool_low,
        "med": tool_med,
        "high": tool_high,
        "crit": tool_crit,
        "disabled": tool_disabled,
    }


def make_caller(agent: Agent, authenticated: bool = True) -> CallerIdentity:
    return CallerIdentity(
        caller_type="AGENT",
        caller_id=agent.id,
        organization_id=agent.organization_id,
        is_authenticated=authenticated,
    )


# ===========================================================================
# 1. Isolated Unit Tests: Check 1 (AUTH)
# ===========================================================================

class TestCheckAuth:
    def test_auth_passed(self, org_and_agent):
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        caller = make_caller(agent)
        res = check_auth(inp, caller)
        assert res.status == CheckStatus.PASSED

    def test_auth_failed_missing_caller(self, org_and_agent):
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        res = check_auth(inp, None)
        assert res.status == CheckStatus.FAILED
        assert "missing" in res.message

    def test_auth_failed_unauthenticated(self, org_and_agent):
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        caller = make_caller(agent, authenticated=False)
        res = check_auth(inp, caller)
        assert res.status == CheckStatus.FAILED
        assert "unauthenticated" in res.message

    def test_auth_failed_agent_mismatch(self, org_and_agent):
        org, agent = org_and_agent
        other_id = uuid.uuid4()
        inp = DecisionInput(agent_id=other_id, tool_name="read_customer", action="read")
        caller = make_caller(agent)
        res = check_auth(inp, caller)
        assert res.status == CheckStatus.FAILED
        assert "mismatch" in res.message


# ===========================================================================
# 2. Isolated Unit Tests: Check 2 (AGENT STATUS)
# ===========================================================================

class TestCheckAgentStatus:
    def test_agent_active_passed(self, db_session, org_and_agent):
        org, agent = org_and_agent
        res, loaded_agent = check_agent_status(db_session, org.id, agent.id)
        assert res.status == CheckStatus.PASSED
        assert loaded_agent.id == agent.id

    def test_agent_not_found_failed(self, db_session, org_and_agent):
        org, _ = org_and_agent
        res, loaded_agent = check_agent_status(db_session, org.id, uuid.uuid4())
        assert res.status == CheckStatus.FAILED
        assert "not found" in res.message

    def test_agent_deleted_failed(self, db_session, org_and_agent):
        org, agent = org_and_agent
        agent.status = "DELETED"
        db_session.flush()
        res, _ = check_agent_status(db_session, org.id, agent.id)
        assert res.status == CheckStatus.FAILED
        assert "deleted" in res.message

    def test_agent_suspended_failed(self, db_session, org_and_agent):
        org, agent = org_and_agent
        agent.status = "SUSPENDED"
        db_session.flush()
        res, _ = check_agent_status(db_session, org.id, agent.id)
        assert res.status == CheckStatus.FAILED
        assert "suspended" in res.message


# ===========================================================================
# 3. Isolated Unit Tests: Check 3 (TOOL PERMISSION)
# ===========================================================================

class TestCheckToolPermission:
    def test_permission_granted_passed(self, db_session, org_and_agent, tools_fixture):
        org, agent = org_and_agent
        res, tool = check_tool_permission(db_session, org.id, agent, "read_customer")
        assert res.status == CheckStatus.PASSED
        assert tool.name == "read_customer"

    def test_tool_not_found_failed(self, db_session, org_and_agent):
        org, agent = org_and_agent
        res, tool = check_tool_permission(db_session, org.id, agent, "non_existent_tool")
        assert res.status == CheckStatus.FAILED
        assert "not found" in res.message

    def test_permission_missing_failed(self, db_session, org_and_agent, tools_fixture):
        org, agent = org_and_agent
        # send_email has no permission granted
        res, tool = check_tool_permission(db_session, org.id, agent, "send_email")
        assert res.status == CheckStatus.FAILED
        assert "no permission grant" in res.message

    def test_permission_explicitly_denied_failed(self, db_session, org_and_agent, tools_fixture):
        org, agent = org_and_agent
        # Explicit is_allowed=False
        perm = AgentToolPermission(
            organization_id=org.id,
            agent_id=agent.id,
            tool_id=tools_fixture["med"].id,
            is_allowed=False,
        )
        db_session.add(perm)
        db_session.flush()

        res, tool = check_tool_permission(db_session, org.id, agent, "send_email")
        assert res.status == CheckStatus.FAILED
        assert "explicitly denied" in res.message


# ===========================================================================
# 4. Isolated Unit Tests: Check 4 (TOOL ENABLED)
# ===========================================================================

class TestCheckToolEnabled:
    def test_tool_enabled_passed(self, tools_fixture):
        res = check_tool_enabled(tools_fixture["low"])
        assert res.status == CheckStatus.PASSED

    def test_tool_disabled_failed(self, tools_fixture):
        res = check_tool_enabled(tools_fixture["disabled"])
        assert res.status == CheckStatus.FAILED
        assert "disabled" in res.message


# ===========================================================================
# 5. Isolated Unit Tests: Check 5 (ACTION ALLOWED)
# ===========================================================================

class TestCheckActionAllowed:
    def test_action_allowed_passed(self, tools_fixture):
        res = check_action_allowed(tools_fixture["low"], "read")
        assert res.status == CheckStatus.PASSED

    def test_empty_action_failed(self, tools_fixture):
        res = check_action_allowed(tools_fixture["low"], "")
        assert res.status == CheckStatus.FAILED
        assert "empty" in res.message


# ===========================================================================
# 6. Isolated Unit Tests: Check 6 (RISK LEVEL)
# ===========================================================================

class TestCheckRiskLevel:
    def test_low_risk_passed_no_hitl(self, db_session, org_and_agent, tools_fixture):
        org, _ = org_and_agent
        res, hitl_required = check_risk_level(db_session, org.id, tools_fixture["low"])
        assert res.status == CheckStatus.PASSED
        assert hitl_required is False

    def test_medium_risk_passed_no_hitl(self, db_session, org_and_agent, tools_fixture):
        org, _ = org_and_agent
        res, hitl_required = check_risk_level(db_session, org.id, tools_fixture["med"])
        assert res.status == CheckStatus.PASSED
        assert hitl_required is False

    def test_high_risk_passed_requires_hitl(self, db_session, org_and_agent, tools_fixture):
        org, _ = org_and_agent
        res, hitl_required = check_risk_level(db_session, org.id, tools_fixture["high"])
        assert res.status == CheckStatus.PASSED
        assert hitl_required is True

    def test_critical_risk_failed_denied(self, db_session, org_and_agent, tools_fixture):
        org, _ = org_and_agent
        res, hitl_required = check_risk_level(db_session, org.id, tools_fixture["crit"])
        assert res.status == CheckStatus.FAILED
        assert "denied by policy" in res.message
        assert hitl_required is False

    def test_table_driven_custom_policy_override(self, db_session, org_and_agent, tools_fixture):
        """Verify custom policy in policies table overrides default rules."""
        org, _ = org_and_agent
        custom_policy = Policy(
            organization_id=org.id,
            name="Strict Risk Policy",
            policy_type="RISK",
            rules={
                "risk_rules": {
                    "LOW": "ALLOW",
                    "MEDIUM": "HITL",   # Custom: medium now requires HITL
                    "HIGH": "DENY",     # Custom: high is now denied
                    "CRITICAL": "DENY",
                }
            },
            is_active=True,
        )
        db_session.add(custom_policy)
        db_session.flush()

        # MEDIUM now flags HITL
        res_med, hitl_med = check_risk_level(db_session, org.id, tools_fixture["med"])
        assert res_med.status == CheckStatus.PASSED
        assert hitl_med is True

        # HIGH now fails (DENIED)
        res_high, hitl_high = check_risk_level(db_session, org.id, tools_fixture["high"])
        assert res_high.status == CheckStatus.FAILED
        assert hitl_high is False


# ===========================================================================
# 7. Isolated Unit Tests: Check 7 (BUDGET)
# ===========================================================================

class TestCheckBudget:
    def test_budget_default_passed(self, db_session, org_and_agent, tools_fixture):
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        res = check_budget(db_session, inp, agent, tools_fixture["low"], default_budget_checker)
        assert res.status == CheckStatus.PASSED

    def test_budget_injected_failure(self, db_session, org_and_agent, tools_fixture):
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")

        def mock_exceeded_budget(db, inp, a, t):
            return False, "Monthly spend limit of $500 reached."

        res = check_budget(db_session, inp, agent, tools_fixture["low"], mock_exceeded_budget)
        assert res.status == CheckStatus.FAILED
        assert "spend limit" in res.message


# ===========================================================================
# 8. Isolated Unit Tests: Check 8 (RATE LIMIT)
# ===========================================================================

class TestCheckRateLimit:
    def test_rate_limit_default_passed(self, db_session, org_and_agent, tools_fixture):
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        res = check_rate_limit(db_session, inp, agent, tools_fixture["low"], default_rate_limit_checker)
        assert res.status == CheckStatus.PASSED

    def test_rate_limit_injected_failure(self, db_session, org_and_agent, tools_fixture):
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")

        def mock_rate_limited(db, inp, a, t):
            return False, "Rate limit exceeded: 60 requests/minute."

        res = check_rate_limit(db_session, inp, agent, tools_fixture["low"], mock_rate_limited)
        assert res.status == CheckStatus.FAILED
        assert "60 requests/minute" in res.message


# ===========================================================================
# 9. Isolated Unit Tests: Check 9 (HITL)
# ===========================================================================

class TestCheckHITL:
    def test_hitl_not_required(self, tools_fixture):
        res, is_pending = check_hitl(False, tools_fixture["low"])
        assert res.status == CheckStatus.PASSED
        assert is_pending is False

    def test_hitl_required_produces_pending(self, tools_fixture):
        res, is_pending = check_hitl(True, tools_fixture["high"])
        assert res.status == CheckStatus.PASSED
        assert is_pending is True
        assert "queued for human approval" in res.message


# ===========================================================================
# 10. Isolated Unit Tests: Check 10 (PROHIBITED PARAMETERS)
# ===========================================================================

class TestCheckProhibitedParameters:
    def test_clean_parameters_passed(self, db_session, org_and_agent):
        org, _ = org_and_agent
        params = {"customer_id": 42, "reason": "Standard inquiry"}
        res = check_prohibited_parameters(db_session, org.id, params)
        assert res.status == CheckStatus.PASSED

    def test_destructive_sql_pattern_failed(self, db_session, org_and_agent):
        org, _ = org_and_agent
        params = {"query": "SELECT * FROM users; DROP TABLE accounts;"}
        res = check_prohibited_parameters(db_session, org.id, params)
        assert res.status == CheckStatus.FAILED
        assert "Prohibited parameter" in res.message

    def test_destructive_shell_pattern_failed(self, db_session, org_and_agent):
        org, _ = org_and_agent
        params = {"script": "rm -rf /var/data"}
        res = check_prohibited_parameters(db_session, org.id, params)
        assert res.status == CheckStatus.FAILED
        assert "Prohibited parameter" in res.message

    def test_data_driven_custom_denylist(self, db_session, org_and_agent):
        org, _ = org_and_agent
        custom_policy = Policy(
            organization_id=org.id,
            name="Custom Denylist",
            policy_type="PARAM_DENYLIST",
            rules={"patterns": [r"(?i)\bbanned_keyword\b"]},
            is_active=True,
        )
        db_session.add(custom_policy)
        db_session.flush()

        res = check_prohibited_parameters(db_session, org.id, {"note": "This has banned_keyword inside"})
        assert res.status == CheckStatus.FAILED
        assert "banned_keyword" in res.message


# ===========================================================================
# 11. Isolated Unit Tests: Check 11 (SUSPICIOUS REQUEST)
# ===========================================================================

class TestCheckSuspiciousRequest:
    def test_normal_payload_passed(self, org_and_agent):
        _, agent = org_and_agent
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="read_customer",
            action="read",
            parameters={"id": 1},
            estimated_tokens=500,
            estimated_cost=0.01,
        )
        res = check_suspicious_request(inp)
        assert res.status == CheckStatus.PASSED

    def test_oversized_payload_failed(self, org_and_agent):
        _, agent = org_and_agent
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="read_customer",
            action="read",
            parameters={"huge": "x" * 70000},  # > 64 KB
        )
        res = check_suspicious_request(inp)
        assert res.status == CheckStatus.FAILED
        assert "payload size" in res.message

    def test_excessive_tokens_failed(self, org_and_agent):
        _, agent = org_and_agent
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="read_customer",
            action="read",
            estimated_tokens=200000,  # > 100k
        )
        res = check_suspicious_request(inp)
        assert res.status == CheckStatus.FAILED
        assert "estimated tokens" in res.message

    def test_excessive_cost_failed(self, org_and_agent):
        _, agent = org_and_agent
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="read_customer",
            action="read",
            estimated_cost=25000.0,  # > $10,000
        )
        res = check_suspicious_request(inp)
        assert res.status == CheckStatus.FAILED
        assert "estimated cost" in res.message


# ===========================================================================
# 12. Full Pipeline & Precedence Tests
# ===========================================================================

class TestFullPipeline:
    def test_low_risk_permitted_produces_allow(self, db_session, org_and_agent, tools_fixture):
        """LOW-risk tool with permission granted produces ALLOW with no human step."""
        org, agent = org_and_agent
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="read_customer",
            action="read",
            parameters={"customer_id": 101},
        )
        caller = make_caller(agent)
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.ALLOW
        assert out.reason == "All policy checks passed."
        # All checks must have run and passed
        for check_name, res in out.checks.items():
            assert res.status == CheckStatus.PASSED, f"Expected {check_name} to pass"

    def test_high_risk_permitted_produces_pending(self, db_session, org_and_agent, tools_fixture):
        """HIGH-risk tool with permission granted produces PENDING, not ALLOW."""
        org, agent = org_and_agent
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="process_refund",
            action="refund",
            parameters={"amount": 99.99, "currency": "USD"},
        )
        caller = make_caller(agent)
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.PENDING
        assert "requires human approval" in out.reason
        assert out.checks["HITL"].details["is_pending"] is True
        # Parameters checks also ran and passed
        assert out.checks["PROHIBITED_PARAMETERS"].status == CheckStatus.PASSED
        assert out.checks["SUSPICIOUS_REQUEST"].status == CheckStatus.PASSED

    def test_critical_risk_always_denied_regardless_of_permission(
        self, db_session, org_and_agent, tools_fixture
    ):
        """CRITICAL-risk tool is always denied regardless of permissions."""
        org, agent = org_and_agent
        # Agent has explicit permission for delete_database
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="delete_database",
            action="drop",
            parameters={"target": "test_db"},
        )
        caller = make_caller(agent)
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "CRITICAL" in out.reason
        assert out.checks["TOOL_PERMISSION"].status == CheckStatus.PASSED
        assert out.checks["RISK_LEVEL"].status == CheckStatus.FAILED
        # Short-circuits: BUDGET and later checks are SKIPPED
        assert out.checks["BUDGET"].status == CheckStatus.SKIPPED
        assert out.checks["HITL"].status == CheckStatus.SKIPPED

    def test_unpermitted_agent_denied_before_risk_level(
        self, db_session, org_and_agent, tools_fixture
    ):
        """Unpermitted agent is denied before risk level is evaluated
        (proving TOOL PERMISSION runs before RISK LEVEL).
        """
        org, agent = org_and_agent
        # Agent has NO permission for send_email
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="send_email",
            action="send",
            parameters={"to": "user@example.com"},
        )
        caller = make_caller(agent)
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "no permission grant" in out.reason
        assert out.checks["TOOL_PERMISSION"].status == CheckStatus.FAILED
        # RISK_LEVEL must be SKIPPED (proving ordering)
        assert out.checks["RISK_LEVEL"].status == CheckStatus.SKIPPED
        assert out.checks["BUDGET"].status == CheckStatus.SKIPPED

    def test_prohibited_parameters_overrides_hitl_pending(
        self, db_session, org_and_agent, tools_fixture
    ):
        """DENY from PROHIBITED PARAMETERS overrides what would otherwise be a PENDING from HITL.
        Precedence: DENY > PENDING.
        """
        org, agent = org_and_agent
        # process_refund is HIGH risk -> would be PENDING, but parameter has SQL injection
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="process_refund",
            action="refund",
            parameters={"reason": "Normal refund; DROP TABLE users;"},
        )
        caller = make_caller(agent)
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "Prohibited parameter" in out.reason
        # HITL ran and flagged pending, but final decision is DENY
        assert out.checks["HITL"].details["is_pending"] is True
        assert out.checks["PROHIBITED_PARAMETERS"].status == CheckStatus.FAILED

    def test_suspicious_request_overrides_hitl_pending(
        self, db_session, org_and_agent, tools_fixture
    ):
        """DENY from SUSPICIOUS REQUEST overrides PENDING from HITL."""
        org, agent = org_and_agent
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="process_refund",
            action="refund",
            parameters={"huge": "x" * 70000},
        )
        caller = make_caller(agent)
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "Suspicious request" in out.reason
        assert out.checks["HITL"].details["is_pending"] is True
        assert out.checks["SUSPICIOUS_REQUEST"].status == CheckStatus.FAILED

    def test_auth_failure_short_circuits_entire_pipeline(self, db_session, org_and_agent):
        """Unauthenticated caller stops at check 1; checks 2-11 are skipped."""
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller=None)

        assert out.decision == DecisionEnum.DENY
        assert out.checks["AUTH"].status == CheckStatus.FAILED
        for check in ["AGENT_STATUS", "TOOL_PERMISSION", "TOOL_ENABLED", "RISK_LEVEL", "BUDGET", "HITL"]:
            assert out.checks[check].status == CheckStatus.SKIPPED

    def test_disabled_tool_short_circuits_pipeline(
        self, db_session, org_and_agent, tools_fixture
    ):
        """Disabled tool fails at check 4 (TOOL ENABLED); checks 5-11 are skipped."""
        org, agent = org_and_agent
        # Give permission for disabled tool
        perm = AgentToolPermission(
            organization_id=org.id,
            agent_id=agent.id,
            tool_id=tools_fixture["disabled"].id,
            is_allowed=True,
        )
        db_session.add(perm)
        db_session.flush()

        inp = DecisionInput(agent_id=agent.id, tool_name="disabled_tool", action="read")
        caller = make_caller(agent)
        engine = PolicyEngine(db=db_session)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "disabled" in out.reason
        assert out.checks["TOOL_PERMISSION"].status == CheckStatus.PASSED
        assert out.checks["TOOL_ENABLED"].status == CheckStatus.FAILED
        assert out.checks["RISK_LEVEL"].status == CheckStatus.SKIPPED

    def test_injected_budget_checker_failure_short_circuits(
        self, db_session, org_and_agent, tools_fixture
    ):
        """Custom budget checker failure stops at check 7 (BUDGET)."""
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        caller = make_caller(agent)

        def mock_budget_fail(db, inp, a, t):
            return False, "Cost cap exceeded"

        engine = PolicyEngine(db=db_session, budget_checker=mock_budget_fail)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "Cost cap exceeded" in out.reason
        assert out.checks["BUDGET"].status == CheckStatus.FAILED
        assert out.checks["RATE_LIMIT"].status == CheckStatus.SKIPPED
        assert out.checks["HITL"].status == CheckStatus.SKIPPED

    def test_injected_rate_limit_checker_failure_short_circuits(
        self, db_session, org_and_agent, tools_fixture
    ):
        """Custom rate limit checker failure stops at check 8 (RATE LIMIT)."""
        org, agent = org_and_agent
        inp = DecisionInput(agent_id=agent.id, tool_name="read_customer", action="read")
        caller = make_caller(agent)

        def mock_rate_fail(db, inp, a, t):
            return False, "Too many requests"

        engine = PolicyEngine(db=db_session, rate_limit_checker=mock_rate_fail)
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "Too many requests" in out.reason
        assert out.checks["BUDGET"].status == CheckStatus.PASSED
        assert out.checks["RATE_LIMIT"].status == CheckStatus.FAILED
        assert out.checks["HITL"].status == CheckStatus.SKIPPED
