"""Pydantic schemas for the AgentGuard Policy Engine (Phase 5).

Defines the input contract (DecisionInput), output contract (DecisionOutput),
check breakdown models (CheckResult, CheckStatus), and caller identity.
"""
import uuid
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class DecisionEnum(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    PENDING = "PENDING"


class CheckStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class CheckResult(BaseModel):
    status: CheckStatus
    message: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class CallerIdentity(BaseModel):
    """Resolved authentication identity passed from upstream middleware/auth."""
    caller_type: str = "AGENT"  # "AGENT" or "USER"
    caller_id: uuid.UUID
    organization_id: uuid.UUID
    is_authenticated: bool = True


class DecisionInput(BaseModel):
    """Input payload to the Policy Engine matching project.md contract."""
    model_config = ConfigDict(extra="ignore")

    agent_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    tool_name: str = Field(..., min_length=1, max_length=100)
    action: str = Field(..., min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    estimated_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    metadata: Optional[dict[str, Any]] = None


class DecisionOutput(BaseModel):
    """Output decision from the Policy Engine with human-readable reason
    and a 11-step audit/debug checks breakdown.
    """
    decision: DecisionEnum
    reason: str
    checks: dict[str, CheckResult]


class GuardResponse(BaseModel):
    """HTTP response shape for POST /guard/check, matching project.md contract."""
    decision: DecisionEnum
    request_id: uuid.UUID
    reason: str


# ---------------------------------------------------------------------------
# Phase 12: Policy CRUD schemas
# ---------------------------------------------------------------------------

from datetime import datetime  # noqa: E402


class PolicyCreateRequest(BaseModel):
    """Create a new policy rule set.

    `rules` must be a non-empty dict. The policy engine reads at minimum one of:
      - allowed_actions: list[str]
      - blocked_actions: list[str]
      - risk_thresholds: dict mapping risk level -> decision
    Malformed rules are rejected at the API boundary.
    """
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    policy_type: str = Field(..., min_length=1, max_length=50)
    rules: dict[str, Any] = Field(..., description="Non-empty rules dict")
    is_active: bool = True


class PolicyUpdateRequest(BaseModel):
    """PATCH semantics — all fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    policy_type: Optional[str] = Field(None, min_length=1, max_length=50)
    rules: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    policy_type: str
    rules: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
