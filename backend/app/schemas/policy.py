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
