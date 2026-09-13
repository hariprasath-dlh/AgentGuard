"""Policy CRUD endpoints (Phase 12).

RBAC matrix:
  - GET /policies:         ADMIN, SECURITY, AUDITOR, MANAGER  (read)
  - POST /policies:        ADMIN, SECURITY
  - PATCH /policies/{id}:  ADMIN, SECURITY
  - DELETE /policies/{id}: ADMIN, SECURITY  (soft-delete → is_active=False)

Rules JSON is validated at the API boundary:
  - Must be a non-empty dict.
  - Must contain at least one recognised key: allowed_actions, blocked_actions,
    risk_thresholds, or max_cost_per_call. Bad structures are rejected with 422.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.policy import PolicyRepository
from app.schemas.auth import RoleEnum
from app.schemas.policy import (
    PolicyCreateRequest,
    PolicyResponse,
    PolicyUpdateRequest,
)
from app.security.deps import AuthenticatedUser, require_role

router = APIRouter(prefix="/policies", tags=["policies"])

_READER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.AUDITOR, RoleEnum.MANAGER)
_WRITER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY)

# Keys the Phase 5 policy engine recognises in the rules dict.
_VALID_RULE_KEYS = {"allowed_actions", "blocked_actions", "risk_thresholds", "max_cost_per_call"}


def _validate_rules(rules: dict) -> None:
    """Raise 422 if rules is empty or has no recognised top-level key."""
    if not rules:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Policy `rules` must be a non-empty dict",
        )
    if not _VALID_RULE_KEYS.intersection(rules.keys()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Policy `rules` must contain at least one recognised key: "
                f"{sorted(_VALID_RULE_KEYS)}"
            ),
        )


@router.get("", response_model=List[PolicyResponse])
def list_policies(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """List all policies (active and inactive) for the caller's organization."""
    repo = PolicyRepository(db=db, organization_id=current_user.organization_id)
    return repo.list_all()


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    request: PolicyCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_WRITER_ROLES)),
):
    """Create a new policy. Rules are validated at the API boundary."""
    _validate_rules(request.rules)

    repo = PolicyRepository(db=db, organization_id=current_user.organization_id)
    if repo.get_by_name(request.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Policy '{request.name}' already exists in this organization",
        )

    policy = repo.create(
        name=request.name,
        description=request.description,
        policy_type=request.policy_type,
        rules=request.rules,
        is_active=request.is_active,
    )
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: uuid.UUID,
    request: PolicyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_WRITER_ROLES)),
):
    """Update a policy. Validates rules if provided."""
    repo = PolicyRepository(db=db, organization_id=current_user.organization_id)
    policy = repo.get_by_id(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    if request.rules is not None:
        _validate_rules(request.rules)

    if request.name and request.name != policy.name:
        if repo.get_by_name(request.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Policy name '{request.name}' already in use",
            )

    update_fields = request.model_dump(exclude_unset=True)
    repo.update(policy, **update_fields)
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_WRITER_ROLES)),
):
    """Soft-delete a policy (is_active → False).

    Hard delete is avoided so that historical tool_request rows that reference
    this policy_id still resolve for auditing purposes.
    """
    repo = PolicyRepository(db=db, organization_id=current_user.organization_id)
    policy = repo.get_by_id(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    repo.soft_delete(policy)
    db.commit()
