"""Pydantic schemas for Dashboard monitoring endpoints (Phase 12)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

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
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    decision: str
    reason: Optional[str] = None
    latency_ms: Optional[float] = None
    created_at: datetime


class ActivityFeed(BaseModel):
    total: int
    items: List[ActivityItem]
