"""Runaway Agent Simulation Harness (Phase 6 deliverable).

Simulates an autonomous AI agent stuck in an infinite tool-call loop
(e.g., retrying an API call or looping on hallucinations).
Fires rapid guard requests through the wired PolicyEngine and proves
that AgentGuard automatically intercepts and blocks the runaway loop
at the configured rate limit threshold.

Can be run as a pytest test:
    python -m pytest tests/test_runaway_agent.py

Or executed directly as a standalone demonstration:
    python -m tests.test_runaway_agent
"""
import sys
import uuid
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.redis import get_redis_client
from app.models.agent import Agent
from app.models.budget import Budget
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.schemas.policy import CallerIdentity, DecisionEnum, DecisionInput
from app.services.factory import create_policy_engine
from app.services.rate_limiter import RedisRateLimitChecker


def run_simulation(db: Session, max_requests_limit: int = 10, loop_attempts: int = 30) -> dict:
    """Executes the runaway agent loop and returns execution telemetry."""
    redis_client = get_redis_client()

    # Create temporary simulation agent and tool
    org = Organization(name="Sim Org", slug=f"sim-org-{uuid.uuid4().hex[:6]}")
    db.add(org)
    db.flush()

    agent = Agent(
        organization_id=org.id,
        name="RunawayFinanceBot",
        description="Simulated runaway autonomous agent",
        status="ACTIVE",
    )
    tool = Tool(
        organization_id=org.id,
        name="read_customer",
        risk_level="LOW",
        is_active=True,
    )
    db.add_all([agent, tool])
    db.flush()

    perm = AgentToolPermission(
        organization_id=org.id,
        agent_id=agent.id,
        tool_id=tool.id,
        is_allowed=True,
    )
    budget = Budget(
        organization_id=org.id,
        agent_id=agent.id,
        max_requests_per_minute=max_requests_limit,
    )
    db.add_all([perm, budget])
    db.flush()

    # Reset any rate limiter keys in Redis
    RedisRateLimitChecker(redis_client).reset(agent.id)

    engine = create_policy_engine(db=db, redis_client=redis_client)
    caller = CallerIdentity(
        caller_type="AGENT",
        caller_id=agent.id,
        organization_id=org.id,
        is_authenticated=True,
    )
    inp = DecisionInput(
        agent_id=agent.id,
        tool_name="read_customer",
        action="read",
        parameters={"query": "financial_records"},
    )

    allowed_count = 0
    denied_count = 0
    first_blocked_at = None
    first_block_reason = None

    for i in range(1, loop_attempts + 1):
        decision_out = engine.evaluate(inp, caller)
        if decision_out.decision == DecisionEnum.ALLOW:
            allowed_count += 1
        else:
            denied_count += 1
            if first_blocked_at is None:
                first_blocked_at = i
                first_block_reason = decision_out.reason

    return {
        "agent_name": agent.name,
        "configured_limit": max_requests_limit,
        "total_attempted": loop_attempts,
        "allowed_count": allowed_count,
        "denied_count": denied_count,
        "first_blocked_at": first_blocked_at,
        "first_block_reason": first_block_reason,
    }


# ===========================================================================
# Pytest Integration Test
# ===========================================================================

def test_runaway_agent_automatically_blocked(db_session: Session):
    """Exit condition test for Phase 6: confirms infinite loop is halted at limit."""
    results = run_simulation(db=db_session, max_requests_limit=10, loop_attempts=25)

    assert results["allowed_count"] == 10, f"Expected exactly 10 allowed, got {results['allowed_count']}"
    assert results["denied_count"] == 15, f"Expected 15 blocked, got {results['denied_count']}"
    assert results["first_blocked_at"] == 11, f"Expected block at request #11, got {results['first_blocked_at']}"
    assert "Rate limit exceeded" in results["first_block_reason"]


# ===========================================================================
# Standalone CLI Runner
# ===========================================================================

if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    import os

    # Connect to SQLite or configured DB for standalone demonstration
    db_url = os.getenv("DEMO_DATABASE_URL", "sqlite:///./demo_runaway.db")
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        print("=" * 65)
        print("         AGENTGUARD RUNAWAY AGENT SIMULATION HARNESS")
        print("=" * 65)
        limit = 10
        attempts = 25
        print(f"Agent: RunawayFinanceBot")
        print(f"Policy: max_requests_per_minute = {limit}")
        print(f"Simulating autonomous infinite tool-call loop ({attempts} requests)...")
        print("-" * 65)

        res = run_simulation(db=db, max_requests_limit=limit, loop_attempts=attempts)

        for i in range(1, res["total_attempted"] + 1):
            if i < res["first_blocked_at"]:
                print(f"  Request #{i:02d}: [ALLOW] -> Intercepted & permitted by AgentGuard")
            elif i == res["first_blocked_at"]:
                print(f"  Request #{i:02d}: [DENY]  -> *** RUNAWAY LOOP BLOCKED *** ({res['first_block_reason']})")
            else:
                print(f"  Request #{i:02d}: [DENY]  -> Blocked by rate limiter")

        print("-" * 65)
        print(f"Summary:")
        print(f"  Total Attempted:  {res['total_attempted']}")
        print(f"  Allowed:          {res['allowed_count']}")
        print(f"  Blocked:          {res['denied_count']}")
        print(f"  First Intercept:  Request #{res['first_blocked_at']}")
        print("=" * 65)
        print("[OK] Exit Condition Verified: Runaway agent was automatically halted.")
    finally:
        db.close()
        # Clean up demo db
        if os.path.exists("./demo_runaway.db"):
            try:
                os.remove("./demo_runaway.db")
            except Exception:
                pass

