"""Repository layer for policies.

All mutations and queries enforce organization_id isolation.
"""
import uuid
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.repositories.base import OrgScopedRepository


class PolicyRepository(OrgScopedRepository):
    def get_by_id(self, policy_id: uuid.UUID) -> Optional[Policy]:
        return (
            self._base_query(Policy)
            .filter(Policy.id == policy_id)
            .first()
        )

    def get_by_type(self, policy_type: str) -> Optional[Policy]:
        return (
            self._base_query(Policy)
            .filter(Policy.policy_type == policy_type, Policy.is_active == True)
            .first()
        )

    def list_active(self) -> list[Policy]:
        return (
            self._base_query(Policy)
            .filter(Policy.is_active == True)
            .all()
        )

    def create(
        self,
        *,
        name: str,
        policy_type: str,
        rules: dict[str, Any],
        description: Optional[str] = None,
        is_active: bool = True,
    ) -> Policy:
        policy = Policy(
            organization_id=self.organization_id,
            name=name,
            policy_type=policy_type,
            rules=rules,
            description=description,
            is_active=is_active,
        )
        self.db.add(policy)
        self.db.flush()
        return policy
