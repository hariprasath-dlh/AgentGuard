"""Tool registry endpoints.

RBAC matrix:
  - CREATE tool:  ADMIN, SECURITY, DEVELOPER
  - READ tool(s): ADMIN, SECURITY, DEVELOPER, MANAGER, AUDITOR  (all roles)
  - UPDATE tool:  ADMIN, SECURITY   (includes is_active=false to retire a tool)

No DELETE endpoint — tools are retired by setting is_active=false.
This preserves the integrity of historical tool_request rows that reference
tool IDs. The unique constraint on (organization_id, name) still applies to
active tools; a retired tool's name can be reused by creating a new record.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.registry import ToolRepository
from app.schemas.auth import RoleEnum
from app.schemas.registry import (
    ToolCreateRequest,
    ToolResponse,
    ToolUpdateRequest,
)
from app.security.deps import AuthenticatedUser, require_role

router = APIRouter(prefix="/tools", tags=["tools"])

_READER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.DEVELOPER, RoleEnum.MANAGER, RoleEnum.AUDITOR)
_CREATOR_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.DEVELOPER)
_MANAGER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY)


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
def create_tool(
    request: ToolCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_CREATOR_ROLES)),
):
    """Register a new tool in the organization's registry."""
    repo = ToolRepository(db=db, organization_id=current_user.organization_id)
    if repo.get_by_name(request.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool '{request.name}' already exists in this organization",
        )
    tool = repo.create(
        name=request.name,
        description=request.description,
        risk_level=request.risk_level.value,
        is_active=request.is_active,
    )
    db.commit()
    db.refresh(tool)
    return tool


@router.get("", response_model=List[ToolResponse])
def list_tools(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """List all tools (active and inactive) for the current organization."""
    repo = ToolRepository(db=db, organization_id=current_user.organization_id)
    return repo.list_all()


@router.get("/{tool_id}", response_model=ToolResponse)
def get_tool(
    tool_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """Get a single tool by ID."""
    repo = ToolRepository(db=db, organization_id=current_user.organization_id)
    tool = repo.get_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    return tool


@router.patch("/{tool_id}", response_model=ToolResponse)
def update_tool(
    tool_id: uuid.UUID,
    request: ToolUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_MANAGER_ROLES)),
):
    """Update tool metadata including risk level and enabled status.

    Set is_active=false to retire a tool without deleting it.
    ADMIN and SECURITY only.
    """
    repo = ToolRepository(db=db, organization_id=current_user.organization_id)
    tool = repo.get_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    if request.name and request.name != tool.name:
        if repo.get_by_name(request.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tool name '{request.name}' already in use",
            )

    update_fields = request.model_dump(exclude_unset=True)
    if "risk_level" in update_fields and update_fields["risk_level"]:
        update_fields["risk_level"] = update_fields["risk_level"].value

    repo.update(tool, **update_fields)
    db.commit()
    db.refresh(tool)
    return tool
