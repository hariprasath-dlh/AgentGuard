"""AgentGuard Policy Engine (Phase 5).

Deterministic, 11-step policy evaluation pipeline:
  1. AUTH
  2. AGENT STATUS
  3. TOOL PERMISSION
  4. TOOL ENABLED
  5. ACTION ALLOWED
  6. RISK LEVEL (data-driven via policies table)
  7. BUDGET (injected interface, stubbed to pass)
  8. RATE LIMIT (injected interface, stubbed to pass)
  9. HITL (HIGH risk or policy-flagged produces PENDING)
 10. PROHIBITED PARAMETERS (data-driven denylist; DENY overrides PENDING)
 11. SUSPICIOUS REQUEST (explainable payload thresholds; DENY overrides PENDING)

Precedence order: DENY > PENDING > ALLOW.
Golden rule: No LLM calls, no prompt evaluation. Purely deterministic reasoning
over structured input fields.
"""
import json
import re
import uuid
from typing import Any, Callable, Optional, Protocol, Tuple
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.policy import Policy
from app.models.tool import Tool
from app.repositories.policy import PolicyRepository
from app.repositories.registry import AgentRepository, PermissionRepository, ToolRepository
from app.schemas.policy import (
    CallerIdentity,
    CheckResult,
    CheckStatus,
    DecisionEnum,
    DecisionInput,
    DecisionOutput,
)


# ---------------------------------------------------------------------------
# Protocols / Types for Injected Checkers (Phase 6 stubs)
# ---------------------------------------------------------------------------

class BudgetChecker(Protocol):
    def __call__(
        self,
        db: Session,
        input_data: DecisionInput,
        agent: Agent,
        tool: Tool,
    ) -> Tuple[bool, Optional[str]]:
        ...


class RateLimitChecker(Protocol):
    def __call__(
        self,
        db: Session,
        input_data: DecisionInput,
        agent: Agent,
        tool: Tool,
    ) -> Tuple[bool, Optional[str]]:
        ...


def default_budget_checker(
    db: Session,
    input_data: DecisionInput,
    agent: Agent,
    tool: Tool,
) -> Tuple[bool, Optional[str]]:
    """Phase 6 stub: always passes. Real Redis-backed check injected in Phase 6."""
    return True, None


def default_rate_limit_checker(
    db: Session,
    input_data: DecisionInput,
    agent: Agent,
    tool: Tool,
) -> Tuple[bool, Optional[str]]:
    """Phase 6 stub: always passes. Real Redis-backed check injected in Phase 6."""
    return True, None


# ---------------------------------------------------------------------------
# Default Policy Rule Configurations (Data-driven fallback)
# ---------------------------------------------------------------------------

DEFAULT_RISK_RULES = {
    "LOW": "ALLOW",
    "MEDIUM": "ALLOW",
    "HIGH": "HITL",
    "CRITICAL": "DENY",
}

DEFAULT_PROHIBITED_PATTERNS = [
    r"(?i)\bdrop\s+table\b",
    r"(?i)\bdelete\s+from\b",
    r"(?i)\btruncate\s+table\b",
    r"(?i)\balter\s+table\b",
    r"(?i)\brm\s+-rf\b",
    r"(?i)\bmkfs\b",
    r"(?i)\bformat\s+[a-z]:",
    r"(?i)\bchmod\s+-R\s+777\b",
    r"(?i)\bshutdown\b",
    r"(?i)\bsudo\s+rm\b",
    r">\s*/dev/sd[a-z]",
]

MAX_PARAM_PAYLOAD_BYTES = 65536     # 64 KB
MAX_PARAM_KEY_COUNT = 50
MAX_ESTIMATED_TOKENS = 100000
MAX_ESTIMATED_COST = 10000.0


# ---------------------------------------------------------------------------
# Individual Check Functions (Independently Testable)
# ---------------------------------------------------------------------------

def check_auth(
    input_data: DecisionInput,
    caller: Optional[CallerIdentity],
) -> CheckResult:
    """Check 1: AUTH.
    Confirms caller identity is present, authenticated, and well-formed.
    """
    if caller is None:
        return CheckResult(
            status=CheckStatus.FAILED,
            message="Authentication required: caller identity is missing.",
        )
    if not caller.is_authenticated:
        return CheckResult(
            status=CheckStatus.FAILED,
            message="Caller is unauthenticated.",
        )
    if not caller.caller_id or not caller.organization_id:
        return CheckResult(
            status=CheckStatus.FAILED,
            message="Caller identity is malformed: missing caller_id or organization_id.",
        )
    if caller.caller_type == "AGENT" and caller.caller_id != input_data.agent_id:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Agent identity mismatch: caller '{caller.caller_id}' cannot act as agent '{input_data.agent_id}'.",
        )
    return CheckResult(
        status=CheckStatus.PASSED,
        message="Caller identity authenticated.",
        details={"caller_id": str(caller.caller_id), "caller_type": caller.caller_type},
    )


def check_agent_status(
    db: Session,
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> Tuple[CheckResult, Optional[Agent]]:
    """Check 2: AGENT STATUS.
    Verifies agent exists in the organization and is ACTIVE (not soft-deleted or suspended).
    """
    agent = AgentRepository(db=db, organization_id=org_id).get_by_id(agent_id)
    if not agent:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Agent '{agent_id}' not found in organization.",
        ), None

    if agent.status == "DELETED":
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Agent '{agent.name}' has been deleted.",
        ), agent

    if agent.status == "SUSPENDED":
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Agent '{agent.name}' is suspended.",
        ), agent

    if agent.status != "ACTIVE":
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Agent '{agent.name}' is not active (status: {agent.status}).",
        ), agent

    return CheckResult(
        status=CheckStatus.PASSED,
        message=f"Agent '{agent.name}' is active.",
        details={"agent_id": str(agent.id), "status": agent.status},
    ), agent


def check_tool_permission(
    db: Session,
    org_id: uuid.UUID,
    agent: Agent,
    tool_name: str,
) -> Tuple[CheckResult, Optional[Tool]]:
    """Check 3: TOOL PERMISSION.
    Verifies agent has an explicit, active agent_tool_permissions grant for this tool.
    Uses PermissionRepository indexed lookup on (agent_id, tool_id).
    """
    tool = ToolRepository(db=db, organization_id=org_id).get_by_name(tool_name)
    if not tool:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Tool '{tool_name}' not found in organization.",
        ), None

    perm = PermissionRepository(db=db, organization_id=org_id).get(agent.id, tool.id)
    if not perm:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Agent '{agent.name}' has no permission grant for tool '{tool_name}'.",
        ), tool

    if not perm.is_allowed:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Permission for agent '{agent.name}' to use tool '{tool_name}' is explicitly denied.",
        ), tool

    return CheckResult(
        status=CheckStatus.PASSED,
        message=f"Agent '{agent.name}' is permitted to use tool '{tool_name}'.",
        details={"tool_id": str(tool.id)},
    ), tool


def check_tool_enabled(tool: Tool) -> CheckResult:
    """Check 4: TOOL ENABLED.
    Confirms tool's is_active flag is True.
    """
    if not tool.is_active:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Tool '{tool.name}' is disabled.",
        )
    return CheckResult(
        status=CheckStatus.PASSED,
        message=f"Tool '{tool.name}' is enabled.",
    )


def check_action_allowed(tool: Tool, action: str) -> CheckResult:
    """Check 5: ACTION ALLOWED.
    Validates requested action. Per Phase 2 schema, Tool has no sub-actions table,
    so non-empty actions pass through.
    """
    if not action or not action.strip():
        return CheckResult(
            status=CheckStatus.FAILED,
            message="Requested action cannot be empty.",
        )
    return CheckResult(
        status=CheckStatus.PASSED,
        message=f"Action '{action}' is permitted for tool '{tool.name}'.",
        details={"action": action},
    )


def check_risk_level(
    db: Session,
    org_id: uuid.UUID,
    tool: Tool,
) -> Tuple[CheckResult, bool]:
    """Check 6: RISK LEVEL.
    Data-driven policy lookup from the policies table for policy_type='RISK'.
    Returns (CheckResult, hitl_required: bool).
      - CRITICAL: DENY
      - HIGH: PASS with hitl_required=True
      - MEDIUM / LOW: PASS with hitl_required=False
    """
    policy_repo = PolicyRepository(db=db, organization_id=org_id)
    risk_policy = policy_repo.get_by_type("RISK")

    rules = DEFAULT_RISK_RULES
    if risk_policy and isinstance(risk_policy.rules, dict):
        rules = risk_policy.rules.get("risk_rules", risk_policy.rules)

    risk_level = (tool.risk_level or "LOW").upper()
    action = rules.get(risk_level, "DENY")

    if action == "DENY":
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Tool '{tool.name}' has risk level '{risk_level}', which is denied by policy.",
            details={"risk_level": risk_level, "rule_action": action},
        ), False

    if action == "HITL":
        return CheckResult(
            status=CheckStatus.PASSED,
            message=f"Tool '{tool.name}' has risk level '{risk_level}', which requires human approval (HITL).",
            details={"risk_level": risk_level, "rule_action": action, "hitl_required": True},
        ), True

    if action == "ALLOW":
        return CheckResult(
            status=CheckStatus.PASSED,
            message=f"Tool '{tool.name}' risk level '{risk_level}' is acceptable.",
            details={"risk_level": risk_level, "rule_action": action},
        ), False

    return CheckResult(
        status=CheckStatus.FAILED,
        message=f"Unrecognized policy action '{action}' for risk level '{risk_level}'.",
    ), False


def check_budget(
    db: Session,
    input_data: DecisionInput,
    agent: Agent,
    tool: Tool,
    budget_checker: BudgetChecker,
) -> CheckResult:
    """Check 7: BUDGET.
    Evaluates budget constraints via injected checker (stub in Phase 5, Redis in Phase 6).
    """
    allowed, reason = budget_checker(db, input_data, agent, tool)
    if not allowed:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=reason or "Budget limit exceeded.",
        )
    return CheckResult(
        status=CheckStatus.PASSED,
        message="Budget check passed.",
    )


def check_rate_limit(
    db: Session,
    input_data: DecisionInput,
    agent: Agent,
    tool: Tool,
    rate_limit_checker: RateLimitChecker,
) -> CheckResult:
    """Check 8: RATE LIMIT.
    Evaluates sliding-window rate limits via injected checker (stub in Phase 5, Redis in Phase 6).
    """
    allowed, reason = rate_limit_checker(db, input_data, agent, tool)
    if not allowed:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=reason or "Rate limit exceeded.",
        )
    return CheckResult(
        status=CheckStatus.PASSED,
        message="Rate limit check passed.",
    )


def check_hitl(
    hitl_required: bool,
    tool: Tool,
) -> Tuple[CheckResult, bool]:
    """Check 9: HITL.
    Determines if action requires human approval.
    Returns (CheckResult, is_pending: bool).
    """
    if hitl_required:
        return CheckResult(
            status=CheckStatus.PASSED,
            message=f"Action on tool '{tool.name}' queued for human approval (HITL).",
            details={"is_pending": True},
        ), True

    return CheckResult(
        status=CheckStatus.PASSED,
        message="No human approval required.",
        details={"is_pending": False},
    ), False


def check_prohibited_parameters(
    db: Session,
    org_id: uuid.UUID,
    parameters: dict[str, Any],
) -> CheckResult:
    """Check 10: PROHIBITED PARAMETERS.
    Pragmatic guardrail against destructive payload patterns (SQL injection, shell drops).
    Data-driven: reads from policies table (policy_type='PARAM_DENYLIST') with fallback defaults.
    """
    policy_repo = PolicyRepository(db=db, organization_id=org_id)
    denylist_policy = policy_repo.get_by_type("PARAM_DENYLIST")

    patterns = DEFAULT_PROHIBITED_PATTERNS
    if denylist_policy and isinstance(denylist_policy.rules, dict):
        patterns = denylist_policy.rules.get("patterns", DEFAULT_PROHIBITED_PATTERNS)

    compiled = [re.compile(p) for p in patterns]

    def _inspect_value(val: Any) -> Optional[str]:
        if isinstance(val, str):
            for pattern in compiled:
                if pattern.search(val):
                    return pattern.pattern
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(k, str):
                    for pattern in compiled:
                        if pattern.search(k):
                            return pattern.pattern
                res = _inspect_value(v)
                if res:
                    return res
        elif isinstance(val, list):
            for item in val:
                res = _inspect_value(item)
                if res:
                    return res
        return None

    matched = _inspect_value(parameters)
    if matched:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Prohibited parameter pattern detected: '{matched}'.",
            details={"matched_pattern": matched},
        )

    return CheckResult(
        status=CheckStatus.PASSED,
        message="No prohibited parameters detected.",
    )


def check_suspicious_request(input_data: DecisionInput) -> CheckResult:
    """Check 11: SUSPICIOUS REQUEST.
    Simple, explainable heuristic: flags anomalous payload size, token estimates, or costs.
    """
    try:
        param_bytes = len(json.dumps(input_data.parameters))
    except Exception:
        param_bytes = len(str(input_data.parameters))

    if param_bytes > MAX_PARAM_PAYLOAD_BYTES:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Suspicious request: parameter payload size ({param_bytes} bytes) exceeds limit ({MAX_PARAM_PAYLOAD_BYTES} bytes).",
            details={"payload_bytes": param_bytes, "limit": MAX_PARAM_PAYLOAD_BYTES},
        )

    if len(input_data.parameters) > MAX_PARAM_KEY_COUNT:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Suspicious request: parameter count ({len(input_data.parameters)}) exceeds limit ({MAX_PARAM_KEY_COUNT}).",
            details={"key_count": len(input_data.parameters), "limit": MAX_PARAM_KEY_COUNT},
        )

    if input_data.estimated_tokens > MAX_ESTIMATED_TOKENS:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Suspicious request: estimated tokens ({input_data.estimated_tokens}) exceeds safety limit ({MAX_ESTIMATED_TOKENS}).",
            details={"estimated_tokens": input_data.estimated_tokens, "limit": MAX_ESTIMATED_TOKENS},
        )

    if input_data.estimated_cost > MAX_ESTIMATED_COST:
        return CheckResult(
            status=CheckStatus.FAILED,
            message=f"Suspicious request: estimated cost (${input_data.estimated_cost}) exceeds limit (${MAX_ESTIMATED_COST}).",
            details={"estimated_cost": input_data.estimated_cost, "limit": MAX_ESTIMATED_COST},
        )

    return CheckResult(
        status=CheckStatus.PASSED,
        message="Request payload within normal operational thresholds.",
    )


# ---------------------------------------------------------------------------
# The Policy Engine Orchestrator
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Deterministic policy evaluation engine.

    Executes 11 checks in strict sequence:
      1. AUTH
      2. AGENT STATUS
      3. TOOL PERMISSION
      4. TOOL ENABLED
      5. ACTION ALLOWED
      6. RISK LEVEL
      7. BUDGET
      8. RATE LIMIT
      9. HITL
     10. PROHIBITED PARAMETERS
     11. SUSPICIOUS REQUEST

    Precedence: DENY > PENDING > ALLOW.
    """

    def __init__(
        self,
        db: Session,
        budget_checker: Optional[BudgetChecker] = None,
        rate_limit_checker: Optional[RateLimitChecker] = None,
    ):
        self.db = db
        self.budget_checker = budget_checker or default_budget_checker
        self.rate_limit_checker = rate_limit_checker or default_rate_limit_checker

    def evaluate(
        self,
        input_data: DecisionInput,
        caller: Optional[CallerIdentity] = None,
    ) -> DecisionOutput:
        """Evaluate a tool-call request through the deterministic pipeline."""
        checks: dict[str, CheckResult] = {
            "AUTH": CheckResult(status=CheckStatus.SKIPPED),
            "AGENT_STATUS": CheckResult(status=CheckStatus.SKIPPED),
            "TOOL_PERMISSION": CheckResult(status=CheckStatus.SKIPPED),
            "TOOL_ENABLED": CheckResult(status=CheckStatus.SKIPPED),
            "ACTION_ALLOWED": CheckResult(status=CheckStatus.SKIPPED),
            "RISK_LEVEL": CheckResult(status=CheckStatus.SKIPPED),
            "BUDGET": CheckResult(status=CheckStatus.SKIPPED),
            "RATE_LIMIT": CheckResult(status=CheckStatus.SKIPPED),
            "HITL": CheckResult(status=CheckStatus.SKIPPED),
            "PROHIBITED_PARAMETERS": CheckResult(status=CheckStatus.SKIPPED),
            "SUSPICIOUS_REQUEST": CheckResult(status=CheckStatus.SKIPPED),
        }

        # -------------------------------------------------------------------
        # 1. AUTH
        # -------------------------------------------------------------------
        auth_res = check_auth(input_data, caller)
        checks["AUTH"] = auth_res
        if auth_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=auth_res.message or "Authentication failed.",
                checks=checks,
            )

        org_id = caller.organization_id  # guaranteed present by check_auth

        # -------------------------------------------------------------------
        # 2. AGENT STATUS
        # -------------------------------------------------------------------
        agent_res, agent = check_agent_status(self.db, org_id, input_data.agent_id)
        checks["AGENT_STATUS"] = agent_res
        if agent_res.status == CheckStatus.FAILED or agent is None:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=agent_res.message or "Agent status check failed.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 3. TOOL PERMISSION
        # -------------------------------------------------------------------
        perm_res, tool = check_tool_permission(self.db, org_id, agent, input_data.tool_name)
        checks["TOOL_PERMISSION"] = perm_res
        if perm_res.status == CheckStatus.FAILED or tool is None:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=perm_res.message or "Tool permission check failed.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 4. TOOL ENABLED
        # -------------------------------------------------------------------
        enabled_res = check_tool_enabled(tool)
        checks["TOOL_ENABLED"] = enabled_res
        if enabled_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=enabled_res.message or "Tool enabled check failed.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 5. ACTION ALLOWED
        # -------------------------------------------------------------------
        action_res = check_action_allowed(tool, input_data.action)
        checks["ACTION_ALLOWED"] = action_res
        if action_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=action_res.message or "Action allowed check failed.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 6. RISK LEVEL
        # -------------------------------------------------------------------
        risk_res, hitl_required = check_risk_level(self.db, org_id, tool)
        checks["RISK_LEVEL"] = risk_res
        if risk_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=risk_res.message or "Risk level check failed.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 7. BUDGET
        # -------------------------------------------------------------------
        budget_res = check_budget(self.db, input_data, agent, tool, self.budget_checker)
        checks["BUDGET"] = budget_res
        if budget_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=budget_res.message or "Budget check failed.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 8. RATE LIMIT
        # -------------------------------------------------------------------
        rate_res = check_rate_limit(self.db, input_data, agent, tool, self.rate_limit_checker)
        checks["RATE_LIMIT"] = rate_res
        if rate_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=rate_res.message or "Rate limit check failed.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 9. HITL
        # -------------------------------------------------------------------
        hitl_res, is_pending = check_hitl(hitl_required, tool)
        checks["HITL"] = hitl_res

        # NOTE: Precedence is DENY > PENDING > ALLOW.
        # Even if HITL flagged PENDING, we must still run PROHIBITED_PARAMETERS
        # and SUSPICIOUS_REQUEST first so that a malicious payload is DENIED
        # immediately instead of being routed to human reviewers.

        # -------------------------------------------------------------------
        # 10. PROHIBITED PARAMETERS
        # -------------------------------------------------------------------
        param_res = check_prohibited_parameters(self.db, org_id, input_data.parameters)
        checks["PROHIBITED_PARAMETERS"] = param_res
        if param_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=param_res.message or "Prohibited parameter detected.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # 11. SUSPICIOUS REQUEST
        # -------------------------------------------------------------------
        susp_res = check_suspicious_request(input_data)
        checks["SUSPICIOUS_REQUEST"] = susp_res
        if susp_res.status == CheckStatus.FAILED:
            return DecisionOutput(
                decision=DecisionEnum.DENY,
                reason=susp_res.message or "Suspicious request detected.",
                checks=checks,
            )

        # -------------------------------------------------------------------
        # Final Decision (PENDING or ALLOW)
        # -------------------------------------------------------------------
        if is_pending:
            return DecisionOutput(
                decision=DecisionEnum.PENDING,
                reason=f"Action on tool '{tool.name}' requires human approval (HITL).",
                checks=checks,
            )

        return DecisionOutput(
            decision=DecisionEnum.ALLOW,
            reason="All policy checks passed.",
            checks=checks,
        )
