"""
RecoveryApproval SQLAlchemy model.

Represents an explicit authorization gate before executing a recovery action.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ApprovalStatus,
    RecoveryActionChannel,
    RecoveryActionType,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.recovery import RecoveryAction, RecoveryCase


class RecoveryApproval(Base, TimestampMixin):
    """
    Represents an approval request for executing an AI-recommended recovery action.

    Guarantees:
    - AI recommendations cannot self-execute.
    - Every execution requires an approved RecoveryApproval record.
    """

    __tablename__ = "recovery_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recovery_case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recovery_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recovery_action_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("recovery_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recommendation_id: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
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
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, native_enum=False, length=32),
        default=ApprovalStatus.pending,
        nullable=False,
        index=True,
    )
    requires_human_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase"] = relationship(
        "RecoveryCase",
        back_populates="approvals",
    )
    recovery_action: Mapped[Optional["RecoveryAction"]] = relationship(
        "RecoveryAction",
    )
