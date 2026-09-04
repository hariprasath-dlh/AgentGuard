import typing
import uuid
from decimal import Decimal
from sqlalchemy import ForeignKey, Integer, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if typing.TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.organization import Organization


class Budget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "budgets"

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
        unique=True,
        index=True,
    )
    max_requests_per_minute: Mapped[typing.Optional[int]] = mapped_column(Integer, nullable=True)
    max_requests_per_day: Mapped[typing.Optional[int]] = mapped_column(Integer, nullable=True)
    max_budget_per_session: Mapped[typing.Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    max_budget_per_day: Mapped[typing.Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    current_spend: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="budgets")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="budget")
