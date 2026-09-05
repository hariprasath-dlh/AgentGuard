"""Pydantic schemas for Human-in-the-Loop (HITL) Engine (Phase 9).

Defines request/response contracts for asynchronous human approval, denial,
and queue inspection.
"""
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class HITLReviewRequest(BaseModel):
    """Optional payload when approving or denying a HITL request."""
    review_notes: Optional[str] = None


class HITLRequestResponse(BaseModel):
    """Full detail of a Human-in-the-Loop approval request."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    tool_request_id: uuid.UUID
    status: str  # PENDING, APPROVED, DENIED, EXPIRED
    reviewer_id: Optional[uuid.UUID] = None
    review_notes: Optional[str] = None
    expires_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Contextual metadata from linked ToolRequest
    tool_name: Optional[str] = None
    agent_id: Optional[uuid.UUID] = None
    input_payload: Optional[dict[str, Any]] = None
    output_payload: Optional[dict[str, Any]] = None


class HITLRequestListResponse(BaseModel):
    """Paginated list of HITL requests."""
    total: int
    items: list[HITLRequestResponse]
