import typing
import uuid
from sqlalchemy import Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if typing.TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.audit_log import AuditLog
    from app.models.hitl_request import HITLRequest
    from app.models.organization import Organization
    from app.models.policy import Policy
    from app.models.tool import Tool


class ToolRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tool_requests"

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
    policy_id: Mapped[typing.Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    audit_log_id: Mapped[typing.Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audit_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason: Mapped[typing.Optional[str]] = mapped_column(Text, nullable=True)
    input_payload: Mapped[typing.Optional[dict]] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[typing.Optional[dict]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[typing.Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="tool_requests"
    )
    agent: Mapped["Agent"] = relationship("Agent", back_populates="tool_requests")
    tool: Mapped["Tool"] = relationship("Tool", back_populates="tool_requests")
    policy: Mapped[typing.Optional["Policy"]] = relationship(
        "Policy", back_populates="tool_requests"
    )
    audit_log: Mapped[typing.Optional["AuditLog"]] = relationship(
        "AuditLog", back_populates="tool_requests"
    )
    hitl_request: Mapped[typing.Optional["HITLRequest"]] = relationship(
        "HITLRequest", back_populates="tool_request", uselist=False, cascade="all, delete-orphan"
    )
