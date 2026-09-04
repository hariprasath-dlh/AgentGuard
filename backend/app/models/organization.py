import typing
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if typing.TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.api_key import APIKey
    from app.models.audit_log import AuditLog
    from app.models.budget import Budget
    from app.models.hitl_request import HITLRequest
    from app.models.permission import AgentToolPermission
    from app.models.policy import Policy
    from app.models.role import Role
    from app.models.tool import Tool
    from app.models.tool_request import ToolRequest
    from app.models.user import User


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role", back_populates="organization", cascade="all, delete-orphan"
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="organization", cascade="all, delete-orphan"
    )
    tools: Mapped[list["Tool"]] = relationship(
        "Tool", back_populates="organization", cascade="all, delete-orphan"
    )
    policies: Mapped[list["Policy"]] = relationship(
        "Policy", back_populates="organization", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="organization", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey", back_populates="organization", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["Budget"]] = relationship(
        "Budget", back_populates="organization", cascade="all, delete-orphan"
    )
    tool_requests: Mapped[list["ToolRequest"]] = relationship(
        "ToolRequest", back_populates="organization", cascade="all, delete-orphan"
    )
    hitl_requests: Mapped[list["HITLRequest"]] = relationship(
        "HITLRequest", back_populates="organization", cascade="all, delete-orphan"
    )
    agent_tool_permissions: Mapped[list["AgentToolPermission"]] = relationship(
        "AgentToolPermission", back_populates="organization", cascade="all, delete-orphan"
    )
