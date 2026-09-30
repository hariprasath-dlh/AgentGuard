"""Pydantic schemas for Dashboard monitoring endpoints (Phase 12)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Aggregate numbers for the dashboard home screen, org-scoped."""
    total_agents: int
    total_tools: int
    requests_today: int
    allowed_today: int
    blocked_today: int
    pending_today: int
    total_spend_today: Decimal
    # Budget utilization: list of (agent_id, agent_name, spend, cap)
    budget_utilization: List[dict]


class ActivityItem(BaseModel):
    """Single item in the reverse-chronological activity feed."""
    request_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str | None = None
    tool_name: str | None = None
    decision: str
    reason: str | None = None
    latency_ms: float | None = None
    created_at: datetime


class ActivityFeed(BaseModel):
    total: int
    items: List[ActivityItem]
