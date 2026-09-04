"""Pydantic schemas for the agents + tools registry (Phase 4)."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Agent schemas
# ---------------------------------------------------------------------------

class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    status: AgentStatus = AgentStatus.ACTIVE


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[AgentStatus] = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class AgentCreateResponse(AgentResponse):
    """Returned exactly once on creation — includes the provisioned API key."""
    api_key: str  # plaintext, shown once only
    api_key_id: uuid.UUID
    api_key_prefix: str


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

class ToolCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    risk_level: RiskLevel = RiskLevel.LOW
    is_active: bool = True


class ToolUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    risk_level: Optional[RiskLevel] = None
    is_active: Optional[bool] = None


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    risk_level: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Permission schemas
# ---------------------------------------------------------------------------

class PermissionGrantRequest(BaseModel):
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    is_allowed: bool = True


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    is_allowed: bool
    created_at: datetime
    updated_at: datetime


class PermissionRevokeResponse(BaseModel):
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    revoked: bool = True
