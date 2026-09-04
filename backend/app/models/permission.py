import typing
import uuid
from sqlalchemy import Boolean, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if typing.TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.organization import Organization
    from app.models.tool import Tool


class AgentToolPermission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_tool_permissions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool_permissions"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="agent_tool_permissions"
    )
    agent: Mapped["Agent"] = relationship("Agent", back_populates="permissions")
    tool: Mapped["Tool"] = relationship("Tool", back_populates="permissions")
