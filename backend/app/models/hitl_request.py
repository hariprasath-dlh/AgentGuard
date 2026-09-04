import typing
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if typing.TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.tool_request import ToolRequest
    from app.models.user import User


class HITLRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "hitl_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    reviewer_id: Mapped[typing.Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_notes: Mapped[typing.Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[typing.Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_at: Mapped[typing.Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="hitl_requests"
    )
    tool_request: Mapped["ToolRequest"] = relationship(
        "ToolRequest", back_populates="hitl_request"
    )
    reviewer: Mapped[typing.Optional["User"]] = relationship(
        "User", back_populates="reviewed_hitl_requests"
    )
