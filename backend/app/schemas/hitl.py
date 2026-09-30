"""Pydantic schemas for Human-in-the-Loop (HITL) Engine (Phase 9).

Defines request/response contracts for asynchronous human approval, denial,
and queue inspection.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class HITLReviewRequest(BaseModel):
    """Optional payload when approving or denying a HITL request."""
    review_notes: str | None = None


class HITLRequestResponse(BaseModel):
    """Full detail of a Human-in-the-Loop approval request."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    tool_request_id: uuid.UUID
    status: str  # PENDING, APPROVED, DENIED, EXPIRED
    reviewer_id: uuid.UUID | None = None
    review_notes: str | None = None
    expires_at: datetime | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Contextual metadata from linked ToolRequest
    tool_name: str | None = None
    agent_id: uuid.UUID | None = None
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None


class HITLRequestListResponse(BaseModel):
    """Paginated list of HITL requests."""
    total: int
    items: list[HITLRequestResponse]
