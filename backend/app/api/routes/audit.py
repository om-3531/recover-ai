"""
Audit REST API endpoints (Read-only).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List audit logs",
)
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (e.g. payment, recovery_case)"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    audit_action: Optional[str] = Query(None, alias="action", description="Filter by action name"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit for pagination"),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Query immutable audit trail records with optional filters."""
    items, total = AuditService.list_audit_logs(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=audit_action,
        skip=skip,
        limit=limit,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
    )
