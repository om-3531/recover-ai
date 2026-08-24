"""
AuditLog SQLAlchemy model.

Maintains an immutable audit trail for actions, decisions, and state transitions
across any domain entity.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """
    Immutable audit log for system, AI, and user actions.

    Uses a generic (entity_type, entity_id) reference so it can attach to any model
    without hard foreign key couplings.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Domain entity name (e.g. payment, recovery_case)"
    )
    entity_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Identifier of the target entity"
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Action name (e.g. state_changed, action_executed)"
    )
    actor: Mapped[str] = mapped_column(
        String(128), default="system", nullable=False, comment="Initiator: system, policy_engine, user, agent"
    )
    # Note: Column named 'metadata' in DB, mapped to 'event_metadata' in Python to avoid
    # colliding with SQLAlchemy DeclarativeBase.metadata
    event_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
    )
