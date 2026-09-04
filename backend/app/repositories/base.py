"""Base repository providing organization-scoped query helpers.

Every organization-scoped query MUST go through these helpers to ensure
tenant isolation. Never do ad-hoc organization_id filtering in endpoints —
always delegate to the repository layer so isolation bugs can't slip in later.
"""
import uuid
from typing import Any, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class OrgScopedRepository:
    """Base repository that enforces organization_id on every query."""

    def __init__(self, db: Session, organization_id: uuid.UUID):
        self.db = db
        self.organization_id = organization_id

    def _base_query(self, model: Type[ModelT]):
        """All queries must be filtered to the current organization."""
        return self.db.query(model).filter(
            model.organization_id == self.organization_id
        )

    def get_by_id(self, model: Type[ModelT], record_id: uuid.UUID) -> Optional[ModelT]:
        """Fetch a single record scoped to the current organization."""
        return (
            self._base_query(model)
            .filter(model.id == record_id)
            .first()
        )

    def list_all(self, model: Type[ModelT], **filters: Any):
        """List all records scoped to the current organization."""
        q = self._base_query(model)
        for attr, value in filters.items():
            q = q.filter(getattr(model, attr) == value)
        return q.all()

    def count(self, model: Type[ModelT]) -> int:
        return self._base_query(model).count()
