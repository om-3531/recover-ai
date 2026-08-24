"""
AuditService business logic.

Records immutable audit entries for all state transitions, creations, and updates
across domain entities.
"""

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditService:
    """Service for creating and querying audit logs."""

    @staticmethod
    def create_audit_log(
        db: Session,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str = "system",
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        """Create and persist an immutable audit trail entry."""
        audit_entry = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            actor=actor,
            event_metadata=metadata,
        )
        db.add(audit_entry)
        db.flush()
        return audit_entry

    @staticmethod
    def list_audit_logs(
        db: Session,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """List audit log entries with optional entity/action filters and pagination."""
        query = select(AuditLog)
        count_query = select(func.count()).select_from(AuditLog)

        if entity_type is not None:
            query = query.where(AuditLog.entity_type == entity_type)
            count_query = count_query.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.where(AuditLog.entity_id == str(entity_id))
            count_query = count_query.where(AuditLog.entity_id == str(entity_id))
        if action is not None:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)

        total = db.scalar(count_query) or 0
        items = list(
            db.scalars(
                query.order_by(AuditLog.timestamp.desc())
                .offset(skip)
                .limit(limit)
            ).all()
        )
        return items, total
