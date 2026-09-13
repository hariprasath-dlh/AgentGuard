"""Pydantic schemas for Budget CRUD (Phase 12)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    max_requests_per_minute: Optional[int] = None
    max_requests_per_day: Optional[int] = None
    max_budget_per_session: Optional[Decimal] = None
    max_budget_per_day: Optional[Decimal] = None
    current_spend: Decimal
    created_at: datetime
    updated_at: datetime


class BudgetUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics."""
    max_requests_per_minute: Optional[int] = Field(None, ge=1)
    max_requests_per_day: Optional[int] = Field(None, ge=1)
    max_budget_per_session: Optional[Decimal] = Field(None, ge=0)
    max_budget_per_day: Optional[Decimal] = Field(None, ge=0)
