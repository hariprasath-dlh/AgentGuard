"""Repository layer for agents, tools, and agent-tool permissions.

All mutations and queries enforce organization_id isolation.
No business logic lives here — only DB access patterns.
"""
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.repositories.base import OrgScopedRepository


# ---------------------------------------------------------------------------
# Agent repository
# ---------------------------------------------------------------------------

class AgentRepository(OrgScopedRepository):
    def get_by_id(self, agent_id: uuid.UUID) -> Optional[Agent]:
        return (
            self._base_query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

    def get_by_name(self, name: str) -> Optional[Agent]:
        return (
            self._base_query(Agent)
            .filter(Agent.name == name)
            .first()
        )

    def list_active(self) -> list[Agent]:
        """List all non-deleted agents (status != DELETED)."""
        return (
            self._base_query(Agent)
            .filter(Agent.status != "DELETED")
            .all()
        )

    def list_all(self) -> list[Agent]:
        return self._base_query(Agent).all()

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        status: str = "ACTIVE",
    ) -> Agent:
        agent = Agent(
            organization_id=self.organization_id,
            name=name,
            description=description,
            status=status,
        )
        self.db.add(agent)
        self.db.flush()
        return agent

    def update(self, agent: Agent, **fields) -> Agent:
        for key, value in fields.items():
            if value is not None:
                setattr(agent, key, value)
        self.db.flush()
        return agent

    def soft_delete(self, agent: Agent) -> Agent:
        """Soft-delete: mark status=DELETED. Preserves audit history."""
        agent.status = "DELETED"
        self.db.flush()
        return agent


# ---------------------------------------------------------------------------
# Tool repository
# ---------------------------------------------------------------------------

class ToolRepository(OrgScopedRepository):
    def get_by_id(self, tool_id: uuid.UUID) -> Optional[Tool]:
        return (
            self._base_query(Tool)
            .filter(Tool.id == tool_id)
            .first()
        )

    def get_by_name(self, name: str) -> Optional[Tool]:
        return (
            self._base_query(Tool)
            .filter(Tool.name == name)
            .first()
        )

    def list_all(self) -> list[Tool]:
        return self._base_query(Tool).all()

    def list_active(self) -> list[Tool]:
        return self._base_query(Tool).filter(Tool.is_active == True).all()

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        risk_level: str = "LOW",
        is_active: bool = True,
    ) -> Tool:
        tool = Tool(
            organization_id=self.organization_id,
            name=name,
            description=description,
            risk_level=risk_level,
            is_active=is_active,
        )
        self.db.add(tool)
        self.db.flush()
        return tool

    def update(self, tool: Tool, **fields) -> Tool:
        for key, value in fields.items():
            if value is not None:
                setattr(tool, key, value)
        self.db.flush()
        return tool


# ---------------------------------------------------------------------------
# Permission repository
# ---------------------------------------------------------------------------

class PermissionRepository(OrgScopedRepository):
    def get(self, agent_id: uuid.UUID, tool_id: uuid.UUID) -> Optional[AgentToolPermission]:
        """Single indexed lookup — what Phase 5 policy engine will call."""
        return (
            self._base_query(AgentToolPermission)
            .filter(
                AgentToolPermission.agent_id == agent_id,
                AgentToolPermission.tool_id == tool_id,
            )
            .first()
        )

    def get_by_id(self, permission_id: uuid.UUID) -> Optional[AgentToolPermission]:
        return (
            self._base_query(AgentToolPermission)
            .filter(AgentToolPermission.id == permission_id)
            .first()
        )

    def list_for_agent(self, agent_id: uuid.UUID) -> list[AgentToolPermission]:
        return (
            self._base_query(AgentToolPermission)
            .filter(AgentToolPermission.agent_id == agent_id)
            .all()
        )

    def list_for_tool(self, tool_id: uuid.UUID) -> list[AgentToolPermission]:
        return (
            self._base_query(AgentToolPermission)
            .filter(AgentToolPermission.tool_id == tool_id)
            .all()
        )

    def list_all(self) -> list[AgentToolPermission]:
        return self._base_query(AgentToolPermission).all()

    def grant(
        self,
        *,
        agent_id: uuid.UUID,
        tool_id: uuid.UUID,
        is_allowed: bool = True,
    ) -> tuple[AgentToolPermission, bool]:
        """Create or update a permission. Returns (permission, created: bool)."""
        existing = self.get(agent_id, tool_id)
        if existing:
            existing.is_allowed = is_allowed
            self.db.flush()
            return existing, False
        perm = AgentToolPermission(
            organization_id=self.organization_id,
            agent_id=agent_id,
            tool_id=tool_id,
            is_allowed=is_allowed,
        )
        self.db.add(perm)
        self.db.flush()
        return perm, True

    def revoke(self, agent_id: uuid.UUID, tool_id: uuid.UUID) -> bool:
        """Hard-delete the permission row. Returns True if it existed."""
        existing = self.get(agent_id, tool_id)
        if not existing:
            return False
        self.db.delete(existing)
        self.db.flush()
        return True
