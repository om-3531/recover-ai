"""
Recovery REST API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.exceptions import NotFoundError
from app.models.audit import AuditLog
from app.models.enums import RecoveryCaseState, RecoveryPriority
from app.models.recovery import RecoveryCase
from app.schemas.recovery import (
    RecoveryActionCreate,
    RecoveryActionResponse,
    RecoveryActionStatusUpdate,
    RecoveryCaseCreate,
    RecoveryCaseListResponse,
    RecoveryCaseResponse,
    RecoveryCaseStateUpdate,
)
from app.schemas.webhooks import RecoveryTimelineEvent, RecoveryTimelineResponse
from app.services.recovery_service import RecoveryService

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post(
    "/cases",
    response_model=RecoveryCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recovery case",
)
def create_recovery_case(
    case_in: RecoveryCaseCreate,
    db: Session = Depends(get_db),
) -> RecoveryCaseResponse:
    """Create a new payment recovery investigation case."""
    case = RecoveryService.create_recovery_case(db=db, case_in=case_in)
    return RecoveryCaseResponse.model_validate(case)


@router.get(
    "/cases",
    response_model=RecoveryCaseListResponse,
    summary="List recovery cases",
)
def list_recovery_cases(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit for pagination"),
    case_state: Optional[RecoveryCaseState] = Query(None, alias="state", description="Filter by case state"),
    priority: Optional[RecoveryPriority] = Query(None, description="Filter by priority"),
    db: Session = Depends(get_db),
) -> RecoveryCaseListResponse:
    """List recovery cases with optional state/priority filtering and pagination."""
    items, total = RecoveryService.list_recovery_cases(
        db=db, skip=skip, limit=limit, state=case_state, priority=priority
    )
    return RecoveryCaseListResponse(
        items=[RecoveryCaseResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/cases/{case_id}",
    response_model=RecoveryCaseResponse,
    summary="Get recovery case by ID",
)
def get_recovery_case(
    case_id: int,
    db: Session = Depends(get_db),
) -> RecoveryCaseResponse:
    """Fetch a single recovery case with associated actions."""
    case = RecoveryService.get_recovery_case_by_id(db=db, case_id=case_id)
    return RecoveryCaseResponse.model_validate(case)


@router.patch(
    "/cases/{case_id}/state",
    response_model=RecoveryCaseResponse,
    summary="Update recovery case state",
)
def update_recovery_case_state(
    case_id: int,
    state_update: RecoveryCaseStateUpdate,
    db: Session = Depends(get_db),
) -> RecoveryCaseResponse:
    """
    Transition a recovery case's state.
    Rejects illegal transitions with HTTP 400 Bad Request.
    """
    case = RecoveryService.update_recovery_case_state(
        db=db, case_id=case_id, state_update=state_update
    )
    return RecoveryCaseResponse.model_validate(case)


@router.post(
    "/cases/{case_id}/actions",
    response_model=RecoveryActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recovery action",
)
def create_recovery_action(
    case_id: int,
    action_in: RecoveryActionCreate,
    db: Session = Depends(get_db),
) -> RecoveryActionResponse:
    """Schedule or record an intervention action on a recovery case."""
    action = RecoveryService.create_recovery_action(
        db=db, case_id=case_id, action_in=action_in
    )
    return RecoveryActionResponse.model_validate(action)


@router.patch(
    "/actions/{action_id}/status",
    response_model=RecoveryActionResponse,
    summary="Update recovery action status",
)
def update_recovery_action_status(
    action_id: int,
    status_update: RecoveryActionStatusUpdate,
    db: Session = Depends(get_db),
) -> RecoveryActionResponse:
    """Update execution status, timestamp, and results of a recovery action."""
    action = RecoveryService.update_recovery_action_status(
        db=db, action_id=action_id, status_update=status_update
    )
    return RecoveryActionResponse.model_validate(action)


@router.get(
    "/cases/{case_id}/timeline",
    response_model=RecoveryTimelineResponse,
    summary="Get timeline of audit events for a recovery case",
)
def get_recovery_case_timeline(
    case_id: int,
    limit: int = Query(50, ge=1, le=200, description="Max events"),
    db: Session = Depends(get_db),
) -> RecoveryTimelineResponse:
    """
    Returns the ordered audit log timeline for a specific recovery case.
    Uses entity_type='recovery_case' with entity_id=case_id.
    """
    # Validate case exists
    case_exists = db.scalar(select(RecoveryCase.id).where(RecoveryCase.id == case_id))
    if case_exists is None:
        raise HTTPException(status_code=404, detail=f"RecoveryCase {case_id} not found")

    entity_id_str = str(case_id)
    count = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.entity_type == "recovery_case",
            AuditLog.entity_id == entity_id_str,
        )
    ) or 0

    rows = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "recovery_case",
                AuditLog.entity_id == entity_id_str,
            )
            .order_by(AuditLog.timestamp.asc())
            .limit(limit)
        ).all()
    )

    events = [
        RecoveryTimelineEvent(
            id=r.id,
            action=r.action,
            actor=r.actor,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            event_metadata=r.event_metadata,
            timestamp=r.timestamp,
        )
        for r in rows
    ]

    return RecoveryTimelineResponse(
        recovery_case_id=case_id,
        events=events,
        total_events=count,
    )
