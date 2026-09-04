"""Agent registry endpoints.

RBAC matrix (enforced here):
  - CREATE agent:    ADMIN, SECURITY, DEVELOPER
  - READ agent(s):   ADMIN, SECURITY, DEVELOPER, MANAGER, AUDITOR  (all roles)
  - UPDATE agent:    ADMIN, SECURITY
  - DELETE agent:    ADMIN, SECURITY  (soft delete — status→DELETED)

POST /agents also provisions one API key for the agent and returns the
plaintext key EXACTLY ONCE in the response body. It is never stored in
plaintext and never returned on any subsequent GET.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.auth import APIKeyRepository
from app.repositories.registry import AgentRepository
from app.schemas.auth import RoleEnum
from app.schemas.registry import (
    AgentCreateRequest,
    AgentCreateResponse,
    AgentResponse,
    AgentUpdateRequest,
)
from app.security.api_key import generate_api_key
from app.security.deps import AuthenticatedUser, get_current_user, require_role

router = APIRouter(prefix="/agents", tags=["agents"])

# Roles that can read agents (all five)
_READER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.DEVELOPER, RoleEnum.MANAGER, RoleEnum.AUDITOR)
# Roles that can create agents
_CREATOR_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY, RoleEnum.DEVELOPER)
# Roles that can mutate/delete agents
_MANAGER_ROLES = (RoleEnum.ADMIN, RoleEnum.SECURITY)


@router.post(
    "",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent(
    request: AgentCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_CREATOR_ROLES)),
):
    """Register a new agent and provision its API key.

    The plaintext API key is returned ONCE in this response and is never
    stored or logged in plaintext. Subsequent GETs return only the prefix.
    """
    repo = AgentRepository(db=db, organization_id=current_user.organization_id)

    # Enforce unique name within org
    if repo.get_by_name(request.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent '{request.name}' already exists in this organization",
        )

    agent = repo.create(
        name=request.name,
        description=request.description,
        status=request.status.value,
    )

    # Provision API key for agent (raw key returned once, hash stored)
    raw_key, key_prefix, _ = generate_api_key(prefix="ag_agent")
    key_repo = APIKeyRepository(db=db, organization_id=current_user.organization_id)
    api_key_record = key_repo.create(
        name=f"agent-key-{agent.name}",
        raw_key=raw_key,
        key_prefix=key_prefix,
        agent_id=agent.id,
    )

    db.commit()
    db.refresh(agent)
    db.refresh(api_key_record)

    return AgentCreateResponse(
        id=agent.id,
        organization_id=agent.organization_id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        api_key=raw_key,           # plaintext — shown ONCE only
        api_key_id=api_key_record.id,
        api_key_prefix=key_prefix,
    )


@router.get("", response_model=List[AgentResponse])
def list_agents(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """List all non-deleted agents for the current organization."""
    repo = AgentRepository(db=db, organization_id=current_user.organization_id)
    return repo.list_active()


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_READER_ROLES)),
):
    """Get a single agent by ID. Returns 404 if not in current org or deleted."""
    repo = AgentRepository(db=db, organization_id=current_user.organization_id)
    agent = repo.get_by_id(agent_id)
    if not agent or agent.status == "DELETED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: uuid.UUID,
    request: AgentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_MANAGER_ROLES)),
):
    """Update agent metadata. ADMIN and SECURITY only."""
    repo = AgentRepository(db=db, organization_id=current_user.organization_id)
    agent = repo.get_by_id(agent_id)
    if not agent or agent.status == "DELETED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # If renaming, check uniqueness
    if request.name and request.name != agent.name:
        if repo.get_by_name(request.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent name '{request.name}' already in use",
            )

    update_fields = request.model_dump(exclude_unset=True)
    if "status" in update_fields and update_fields["status"]:
        update_fields["status"] = update_fields["status"].value

    repo.update(agent, **update_fields)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_MANAGER_ROLES)),
):
    """Soft-delete an agent (status → DELETED).

    Choice: soft delete, not hard delete. Audit logs and tool_requests that
    reference this agent's ID must still resolve for forensic/regulatory use.
    Hard delete would break the audit hash chain. Flagged as a design choice.
    """
    repo = AgentRepository(db=db, organization_id=current_user.organization_id)
    agent = repo.get_by_id(agent_id)
    if not agent or agent.status == "DELETED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    repo.soft_delete(agent)
    db.commit()
