"""
RecoveryExecutionJob SQLAlchemy model.

Represents an asynchronous execution job dispatched to execute an approved recovery action.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import JobStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.approval import RecoveryApproval
    from app.models.recovery import RecoveryAction, RecoveryCase


class RecoveryExecutionJob(Base, TimestampMixin):
    """
    Represents background infrastructure for executing an authorized recovery action.

    Guarantees:
    - Bounded execution with retry limit tracking.
    - Idempotency key uniqueness prevents duplicate external communications.
    - Clear separation between execution infrastructure (Job), authorization (Approval),
      business intervention (RecoveryAction), and domain state (RecoveryCase).
    """

    __tablename__ = "recovery_execution_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recovery_case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recovery_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recovery_approval_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recovery_approvals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recovery_action_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("recovery_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=32),
        default=JobStatus.queued,
        nullable=False,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase"] = relationship(
        "RecoveryCase",
        back_populates="execution_jobs",
    )
    recovery_approval: Mapped["RecoveryApproval"] = relationship(
        "RecoveryApproval",
        back_populates="execution_jobs",
    )
    recovery_action: Mapped[Optional["RecoveryAction"]] = relationship(
        "RecoveryAction",
    )
