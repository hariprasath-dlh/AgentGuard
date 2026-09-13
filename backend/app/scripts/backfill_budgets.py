"""Idempotent backfill script to provision default Budget rows for any existing Agents (Phase 12).

Finds all agents in the database lacking a corresponding row in the 'budgets' table
and creates an initial Budget row with all caps set to None (unlimited).

Usage:
    python -m app.scripts.backfill_budgets
"""
import logging
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.agent import Agent
from app.models.budget import Budget

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("backfill_budgets")


def backfill_missing_budgets(db: Session) -> int:
    """Find all agents without a budget and create a default Budget row (caps=None).

    Returns:
        int: Number of new budget rows created.
    """
    agents_without_budget = (
        db.query(Agent)
        .outerjoin(Budget, Agent.id == Budget.agent_id)
        .filter(Budget.id.is_(None))
        .all()
    )

    count = 0
    for agent in agents_without_budget:
        budget = Budget(
            organization_id=agent.organization_id,
            agent_id=agent.id,
            max_requests_per_minute=None,
            max_requests_per_day=None,
            max_budget_per_session=None,
            max_budget_per_day=None,
        )
        db.add(budget)
        count += 1

    if count > 0:
        db.commit()

    log.info(
        f"Backfill complete: provisioned {count} missing budget row(s) for existing agents."
    )
    return count


def main() -> int:
    """CLI entrypoint."""
    db = SessionLocal()
    try:
        return backfill_missing_budgets(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
