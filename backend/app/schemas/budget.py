"""Pydantic schemas for Budget CRUD (Phase 12)."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    max_requests_per_minute: int | None = None
    max_requests_per_day: int | None = None
    max_budget_per_session: Decimal | None = None
    max_budget_per_day: Decimal | None = None
    current_spend: Decimal
    created_at: datetime
    updated_at: datetime


class BudgetUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics."""
    max_requests_per_minute: int | None = Field(None, ge=1)
    max_requests_per_day: int | None = Field(None, ge=1)
    max_budget_per_session: Decimal | None = Field(None, ge=0)
    max_budget_per_day: Decimal | None = Field(None, ge=0)
