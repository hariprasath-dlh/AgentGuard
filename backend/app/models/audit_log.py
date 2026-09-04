import typing
import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if typing.TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.organization import Organization
    from app.models.tool import Tool
    from app.models.tool_request import ToolRequest


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[typing.Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_id: Mapped[typing.Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    decision: Mapped[typing.Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    payload: Mapped[typing.Optional[dict]] = mapped_column(JSON, nullable=True)
    previous_hash: Mapped[typing.Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence_number: Mapped[typing.Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="audit_logs"
    )
    agent: Mapped[typing.Optional["Agent"]] = relationship("Agent", back_populates="audit_logs")
    tool: Mapped[typing.Optional["Tool"]] = relationship("Tool", back_populates="audit_logs")
    tool_requests: Mapped[list["ToolRequest"]] = relationship(
        "ToolRequest", back_populates="audit_log"
    )
