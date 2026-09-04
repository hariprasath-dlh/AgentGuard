"""Agent-tool permission assignment endpoints.

RBAC matrix:
  - GRANT permission:   ADMIN, SECURITY
  - REVOKE permission:  ADMIN, SECURITY
  - READ permissions:   ADMIN, SECURITY, DEVELOPER, MANAGER, AUDITOR

The permission table (agent_tool_permissions) has a unique constraint on
(agent_id, tool_id). The grant endpoint is an upsert — if the row already
exists, its is_allowed flag is updated rather than returning a 409.
Idempotent double-grant is handled at the repository layer.

The policy engine (Phase 5) will call:
    PermissionRepository(db, org_id).get(agent_id, tool_id)
to get a single indexed lookup on (agent_id, tool_id).
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.registry import PermissionRepository, AgentRepository, ToolRepository
from app.schemas.auth import RoleEnum
from app.schemas.registry import (
    PermissionGrantRequest,
    PermissionResponse,
    PermissionRevokeResponse,
)
from app.security.deps import AuthenticatedUser, require_role

router = APIRouter(prefix="/permissions", tags=["permissions"])

_READER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.DEVELOPER, RoleEnum.MANAGER, RoleEnum.AUDITOR)
_WRITER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY)


def _assert_agent_and_tool_in_org(
    db: Session,
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
) -> None:
    """Verify both agent and tool belong to the requester's organization."""
    agent = AgentRepository(db=db, organization_id=org_id).get_by_id(agent_id)
    if not agent or agent.status == "DELETED":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found in this organization",
        )
    tool = ToolRepository(db=db, organization_id=org_id).get_by_id(tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool {tool_id} not found in this organization",
        )


@router.post("", response_model=PermissionResponse, status_code=status.HTTP_200_OK)
def grant_permission(
    request: PermissionGrantRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_WRITER_ROLES)),
):
    """Grant (or update) an agent's permission to use a tool.

    Idempotent: assigning the same (agent_id, tool_id) twice does not
    duplicate the row — it updates is_allowed and returns 200.
    ADMIN and SECURITY only.
    """
    _assert_agent_and_tool_in_org(
        db, current_user.organization_id, request.agent_id, request.tool_id
    )
    repo = PermissionRepository(db=db, organization_id=current_user.organization_id)
    perm, _ = repo.grant(
        agent_id=request.agent_id,
        tool_id=request.tool_id,
        is_allowed=request.is_allowed,
    )
    db.commit()
    db.refresh(perm)
    return perm


@router.delete(
    "/{agent_id}/{tool_id}",
    response_model=PermissionRevokeResponse,
)
def revoke_permission(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_WRITER_ROLES)),
):
    """Revoke a permission — hard-deletes the permission row.

    Returns 404 if the permission does not exist.
    ADMIN and SECURITY only.
    """
    repo = PermissionRepository(db=db, organization_id=current_user.organization_id)
    removed = repo.revoke(agent_id, tool_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )
    db.commit()
    return PermissionRevokeResponse(agent_id=agent_id, tool_id=tool_id, revoked=True)


@router.get("", response_model=List[PermissionResponse])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """List all agent-tool permissions for the current organization."""
    repo = PermissionRepository(db=db, organization_id=current_user.organization_id)
    return repo.list_all()


@router.get("/agents/{agent_id}", response_model=List[PermissionResponse])
def list_agent_permissions(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """List all tool permissions for a specific agent."""
    # Verify agent is in this org first
    agent = AgentRepository(db=db, organization_id=current_user.organization_id).get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    repo = PermissionRepository(db=db, organization_id=current_user.organization_id)
    return repo.list_for_agent(agent_id)


@router.get("/tools/{tool_id}", response_model=List[PermissionResponse])
def list_tool_permissions(
    tool_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """List all agent permissions for a specific tool."""
    tool = ToolRepository(db=db, organization_id=current_user.organization_id).get_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    repo = PermissionRepository(db=db, organization_id=current_user.organization_id)
    return repo.list_for_tool(tool_id)
