"""
RevenueRecord SQLAlchemy model.

Tracks gross and recoverable amounts, financial recognition state, and recovery linkages.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RevenueStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.recovery import RecoveryCase


class RevenueRecord(Base, TimestampMixin):
    """
    Financial record representing gross and recoverable revenue for a payment.

    Enforces a strict 1:1 relationship with Payment via a unique foreign key.
    Monetary amounts are stored as integers representing paise.
    """

    __tablename__ = "revenue_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payments.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    gross_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Gross revenue amount in paise"
    )
    recoverable_amount: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Recoverable amount in paise"
    )
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[RevenueStatus] = mapped_column(
        Enum(RevenueStatus, native_enum=False, length=32),
        default=RevenueStatus.pending,
        nullable=False,
        index=True,
    )

    # Relationships
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="revenue_record",
    )
    recovery_cases: Mapped[list["RecoveryCase"]] = relationship(
        "RecoveryCase",
        back_populates="revenue_record",
        cascade="all, delete-orphan",
        order_by="RecoveryCase.id",
    )
