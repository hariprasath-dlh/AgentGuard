"""Data models for the AgentGuard SDK.

Mirrors the AgentGuard Core Engine guard/check request and response contracts.
"""
import uuid
from typing import Any, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class GuardRequest(BaseModel):
    """Payload sent to POST /guard/check, matching backend DecisionInput schema."""
    model_config = ConfigDict(extra="ignore")

    agent_id: Optional[Union[uuid.UUID, str]] = None
    tool_name: str = Field(..., min_length=1, max_length=100)
    action: str = Field(default="execute", min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    estimated_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    metadata: Optional[dict[str, Any]] = None


class GuardResult(BaseModel):
    """Result returned from client.guard() on successful evaluation.

    Supports both boolean branching (`if result.allowed: ...`) and inspection
    of the raw decision, server-generated request_id, and policy reason.
    """
    model_config = ConfigDict(extra="ignore")

    allowed: bool
    decision: str  # "ALLOW", "DENY", "PENDING"
    request_id: Optional[str] = None
    reason: str = ""
    raw_response: Optional[dict[str, Any]] = None
