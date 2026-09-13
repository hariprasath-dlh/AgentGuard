"""Repository layer for budgets (Phase 12).

All mutations and queries enforce organization_id isolation.
"""
import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.repositories.base import OrgScopedRepository


class BudgetRepository(OrgScopedRepository):
    def get_by_id(self, budget_id: uuid.UUID) -> Optional[Budget]:
        return (
            self._base_query(Budget)
            .filter(Budget.id == budget_id)
            .first()
        )

    def get_by_agent_id(self, agent_id: uuid.UUID) -> Optional[Budget]:
        return (
            self._base_query(Budget)
            .filter(Budget.agent_id == agent_id)
            .first()
        )

    def list_all(self) -> list[Budget]:
        return self._base_query(Budget).all()

    def create_default(self, agent_id: uuid.UUID) -> Budget:
        """Provision a zero-cap (unlimited) budget row for a new agent."""
        budget = Budget(
            organization_id=self.organization_id,
            agent_id=agent_id,
            max_requests_per_minute=None,
            max_requests_per_day=None,
            max_budget_per_session=None,
            max_budget_per_day=None,
            current_spend=Decimal("0.0"),
        )
        self.db.add(budget)
        self.db.flush()
        return budget

    def update(self, budget: Budget, **fields: Any) -> Budget:
        for key, value in fields.items():
            if value is not None:
                setattr(budget, key, value)
        self.db.flush()
        return budget
