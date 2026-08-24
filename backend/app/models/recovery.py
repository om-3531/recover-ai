"""
RecoveryCase and RecoveryAction SQLAlchemy models.

Represents payment recovery workflows and scheduled/executed recovery actions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RiskStatus,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.revenue import RevenueRecord


class RecoveryCase(Base, TimestampMixin):
    """
    Represents an active or historical recovery investigation for at-risk revenue.

    A single RevenueRecord can have multiple RecoveryCases across retry/reopen cycles.
    """

    __tablename__ = "recovery_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    revenue_record_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("revenue_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    risk_status: Mapped[RiskStatus] = mapped_column(
        Enum(RiskStatus, native_enum=False, length=32),
        default=RiskStatus.medium,
        nullable=False,
        index=True,
    )
    priority: Mapped[RecoveryPriority] = mapped_column(
        Enum(RecoveryPriority, native_enum=False, length=32),
        default=RecoveryPriority.medium,
        nullable=False,
        index=True,
    )
    current_state: Mapped[RecoveryCaseState] = mapped_column(
        Enum(RecoveryCaseState, native_enum=False, length=32),
        default=RecoveryCaseState.open,
        nullable=False,
        index=True,
    )

    # Relationships
    revenue_record: Mapped["RevenueRecord"] = relationship(
        "RevenueRecord",
        back_populates="recovery_cases",
    )
    actions: Mapped[list["RecoveryAction"]] = relationship(
        "RecoveryAction",
        back_populates="recovery_case",
        cascade="all, delete-orphan",
        order_by="RecoveryAction.id",
    )


class RecoveryAction(Base, TimestampMixin):
    """
    Represents a specific intervention or attempt executed during recovery.

    Examples: automated retry, customer payment link generation, reminder notification.
    """

    __tablename__ = "recovery_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recovery_case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recovery_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[RecoveryActionType] = mapped_column(
        Enum(RecoveryActionType, native_enum=False, length=64),
        nullable=False,
        index=True,
    )
    channel: Mapped[RecoveryActionChannel] = mapped_column(
        Enum(RecoveryActionChannel, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    status: Mapped[RecoveryActionStatus] = mapped_column(
        Enum(RecoveryActionStatus, native_enum=False, length=32),
        default=RecoveryActionStatus.pending,
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase"] = relationship(
        "RecoveryCase",
        back_populates="actions",
    )
