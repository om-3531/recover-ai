"""
Payment and PaymentEvent SQLAlchemy models.

Represents Razorpay payments and inbound event/webhook payloads.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentEventProcessingStatus, PaymentMethod, PaymentStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.revenue import RevenueRecord


class Payment(Base, TimestampMixin):
    """
    Represents a payment transaction from Razorpay.

    Amounts are stored in paise (1 INR = 100 paise) as integers.
    Never stores Razorpay API secrets or raw credentials.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    razorpay_payment_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Amount in paise (e.g. 50000 = 500.00 INR)"
    )
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=32),
        default=PaymentStatus.created,
        nullable=False,
        index=True,
    )
    method: Mapped[Optional[PaymentMethod]] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=32),
        nullable=True,
    )
    customer_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    customer_reference: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
    )

    # Relationships
    events: Mapped[list["PaymentEvent"]] = relationship(
        "PaymentEvent",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentEvent.id",
    )
    revenue_record: Mapped[Optional["RevenueRecord"]] = relationship(
        "RevenueRecord",
        back_populates="payment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PaymentEvent(Base, TimestampMixin):
    """
    Represents an event or webhook payload received for a payment.

    Designed for webhook idempotency: `razorpay_event_id` is unique and indexed.
    Duplicate Razorpay events must not create duplicate PaymentEvent records.
    """

    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    razorpay_event_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    processing_status: Mapped[PaymentEventProcessingStatus] = mapped_column(
        Enum(PaymentEventProcessingStatus, native_enum=False, length=32),
        default=PaymentEventProcessingStatus.pending,
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment",
        back_populates="events",
    )
