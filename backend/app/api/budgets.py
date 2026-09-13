"""Budget CRUD endpoints (Phase 12).

No POST — a budget row is automatically provisioned when an agent is created
(POST /agents). PATCH /budgets/{id} updates the caps on the existing row.

RBAC matrix:
  - GET /budgets:         ADMIN, SECURITY, AUDITOR, MANAGER  (read)
  - PATCH /budgets/{id}:  ADMIN, SECURITY
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.budget import BudgetRepository
from app.schemas.auth import RoleEnum
from app.schemas.budget import BudgetResponse, BudgetUpdateRequest
from app.security.deps import AuthenticatedUser, require_role

router = APIRouter(prefix="/budgets", tags=["budgets"])

_READER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.AUDITOR, RoleEnum.MANAGER)
_WRITER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY)


@router.get("", response_model=List[BudgetResponse])
def list_budgets(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """List all agent budgets for the caller's organization."""
    repo = BudgetRepository(db=db, organization_id=current_user.organization_id)
    return repo.list_all()


@router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """Get a single budget by ID."""
    repo = BudgetRepository(db=db, organization_id=current_user.organization_id)
    budget = repo.get_by_id(budget_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: uuid.UUID,
    request: BudgetUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_WRITER_ROLES)),
):
    """Update budget caps for an agent. ADMIN and SECURITY only.

    All fields are optional. Set a field to null to remove the cap (unlimited).
    """
    repo = BudgetRepository(db=db, organization_id=current_user.organization_id)
    budget = repo.get_by_id(budget_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    update_fields = request.model_dump(exclude_unset=True)
    repo.update(budget, **update_fields)
    db.commit()
    db.refresh(budget)
    return budget
