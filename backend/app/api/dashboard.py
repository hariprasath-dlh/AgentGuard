"""Dashboard monitoring endpoints (Phase 12).

Polling-only — no WebSockets/SSE (explicitly deferred per project.md Phase 14).

RBAC: ADMIN, SECURITY, AUDITOR, MANAGER can read both endpoints.

Both queries are written to avoid N+1:
  - /dashboard/stats uses a single aggregation query per metric set.
  - /dashboard/activity uses a single JOIN query with a cursor-style limit/offset.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.agent import Agent
from app.models.budget import Budget
from app.models.tool import Tool
from app.models.tool_request import ToolRequest
from app.schemas.auth import RoleEnum
from app.schemas.dashboard import ActivityFeed, ActivityItem, DashboardStats
from app.security.deps import AuthenticatedUser, require_role

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_READER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.AUDITOR, RoleEnum.MANAGER)


def _today_start() -> datetime:
    """UTC midnight (00:00:00) of the current day — used to scope 'today' metrics.

    Synchronized with Phase 6's daily-cost-limit reset:
    RedisBudgetChecker._get_utc_date() (app/services/budget_guard.py) partitions daily
    spend keys using datetime.now(timezone.utc).strftime("%Y-%m-%d"). Both use UTC
    midnight as the exact daily boundary so 'requests today' and 'total spend today'
    reset in lockstep.
    """
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """Return aggregate numbers for the dashboard home screen.

    All values are scoped to the caller's organization. A single pass over
    tool_requests is used for all decision-count metrics to avoid N+1.
    """
    org_id = current_user.organization_id
    today = _today_start()

    # --- Agent + tool counts (simple, indexed) ---
    total_agents = (
        db.query(func.count(Agent.id))
        .filter(Agent.organization_id == org_id, Agent.status != "DELETED")
        .scalar()
        or 0
    )
    total_tools = (
        db.query(func.count(Tool.id))
        .filter(Tool.organization_id == org_id)
        .scalar()
        or 0
    )

    # --- Single-pass request aggregation for today ---
    # Uses conditional aggregation (CASE WHEN) to avoid separate queries.
    row = (
        db.query(
            func.count(ToolRequest.id).label("requests_today"),
            func.sum(
                case((ToolRequest.decision == "ALLOW", 1), else_=0)
            ).label("allowed_today"),
            func.sum(
                case((ToolRequest.decision == "DENY", 1), else_=0)
            ).label("blocked_today"),
            func.sum(
                case((ToolRequest.decision == "PENDING", 1), else_=0)
            ).label("pending_today"),
        )
        .filter(
            ToolRequest.organization_id == org_id,
            ToolRequest.created_at >= today,
        )
        .one()
    )

    requests_today = row.requests_today or 0
    allowed_today = int(row.allowed_today or 0)
    blocked_today = int(row.blocked_today or 0)
    pending_today = int(row.pending_today or 0)

    # --- Budget spend today across all agents ---
    # current_spend is a running total on the Budget row (updated by Phase 6 guard).
    # Sum it across all agents in the org to get a single figure.
    total_spend_today = (
        db.query(func.coalesce(func.sum(Budget.current_spend), 0))
        .filter(Budget.organization_id == org_id)
        .scalar()
        or Decimal("0.0")
    )

    # --- Budget utilization per agent (for sparklines / progress bars) ---
    # Single JOIN query, no per-agent follow-up.
    budgets = (
        db.query(Agent.id, Agent.name, Budget.current_spend, Budget.max_budget_per_day)
        .join(Budget, Budget.agent_id == Agent.id)
        .filter(Agent.organization_id == org_id, Agent.status != "DELETED")
        .all()
    )
    budget_utilization = [
        {
            "agent_id": str(b.id),
            "agent_name": b.name,
            "current_spend": float(b.current_spend),
            "max_budget_per_day": float(b.max_budget_per_day) if b.max_budget_per_day else None,
        }
        for b in budgets
    ]

    return DashboardStats(
        total_agents=total_agents,
        total_tools=total_tools,
        requests_today=requests_today,
        allowed_today=allowed_today,
        blocked_today=blocked_today,
        pending_today=pending_today,
        total_spend_today=Decimal(str(total_spend_today)),
        budget_utilization=budget_utilization,
    )


@router.get("/activity", response_model=ActivityFeed)
def get_dashboard_activity(
    limit: int = Query(50, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset (cursor)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """Return a reverse-chronological feed of tool requests for polling.

    Uses a single LEFT JOIN query with count to avoid N+1. The frontend should
    poll this endpoint; WebSockets/SSE are explicitly deferred to Phase 14.
    """
    org_id = current_user.organization_id

    base_query = (
        db.query(ToolRequest, Agent.name.label("agent_name"), Tool.name.label("tool_name"))
        .join(Agent, Agent.id == ToolRequest.agent_id)
        .join(Tool, Tool.id == ToolRequest.tool_id)
        .filter(ToolRequest.organization_id == org_id)
    )

    total = base_query.count()
    rows = (
        base_query.order_by(ToolRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: List[ActivityItem] = [
        ActivityItem(
            request_id=req.id,
            agent_id=req.agent_id,
            agent_name=agent_name,
            tool_name=tool_name,
            decision=req.decision,
            reason=req.reason,
            latency_ms=req.latency_ms,
            created_at=req.created_at,
        )
        for req, agent_name, tool_name in rows
    ]

    return ActivityFeed(total=total, items=items)
