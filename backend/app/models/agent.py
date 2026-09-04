import typing
import uuid
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if typing.TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.audit_log import AuditLog
    from app.models.budget import Budget
    from app.models.organization import Organization
    from app.models.permission import AgentToolPermission
    from app.models.tool_request import ToolRequest


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[typing.Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_agents_org_name"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="agents")
    permissions: Mapped[list["AgentToolPermission"]] = relationship(
        "AgentToolPermission", back_populates="agent", cascade="all, delete-orphan"
    )
    budget: Mapped[typing.Optional["Budget"]] = relationship(
        "Budget", back_populates="agent", uselist=False, cascade="all, delete-orphan"
    )
    tool_requests: Mapped[list["ToolRequest"]] = relationship(
        "ToolRequest", back_populates="agent", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="agent")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="agent")
