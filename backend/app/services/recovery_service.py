"""
RecoveryService business logic.

Manages recovery workflows, case state machines, deterministic state transitions,
and bounded recovery actions. Does NOT directly send outbound notifications.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import InvalidStateTransitionError, NotFoundError
from app.models.enums import (
    RecoveryActionStatus,
    RecoveryCaseState,
    RecoveryPriority,
)
from app.models.recovery import RecoveryAction, RecoveryCase
from app.schemas.recovery import (
    RecoveryActionCreate,
    RecoveryActionStatusUpdate,
    RecoveryCaseCreate,
    RecoveryCaseStateUpdate,
)
from app.services.audit_service import AuditService
from app.services.revenue_service import RevenueService

# Deterministic State Transition Matrix for Recovery Cases
ALLOWED_STATE_TRANSITIONS: dict[RecoveryCaseState, set[RecoveryCaseState]] = {
    RecoveryCaseState.open: {
        RecoveryCaseState.open,
        RecoveryCaseState.investigating,
        RecoveryCaseState.action_pending,
        RecoveryCaseState.closed,
        RecoveryCaseState.failed,
    },
    RecoveryCaseState.investigating: {
        RecoveryCaseState.investigating,
        RecoveryCaseState.open,
        RecoveryCaseState.action_pending,
        RecoveryCaseState.recovering,
        RecoveryCaseState.closed,
        RecoveryCaseState.failed,
    },
    RecoveryCaseState.action_pending: {
        RecoveryCaseState.action_pending,
        RecoveryCaseState.investigating,
        RecoveryCaseState.recovering,
        RecoveryCaseState.closed,
        RecoveryCaseState.failed,
    },
    RecoveryCaseState.recovering: {
        RecoveryCaseState.recovering,
        RecoveryCaseState.recovered,
        RecoveryCaseState.failed,
        RecoveryCaseState.action_pending,
        RecoveryCaseState.closed,
    },
    RecoveryCaseState.recovered: {
        RecoveryCaseState.recovered,
        RecoveryCaseState.closed,
    },
    RecoveryCaseState.closed: {
        RecoveryCaseState.closed,
        RecoveryCaseState.open,  # Reopening supported
    },
    RecoveryCaseState.failed: {
        RecoveryCaseState.failed,
        RecoveryCaseState.open,  # Reopening for retry supported
        RecoveryCaseState.closed,
    },
}


class RecoveryService:
    """Service for managing recovery cases, state transitions, and recovery actions."""

    @staticmethod
    def create_recovery_case(
        db: Session,
        case_in: RecoveryCaseCreate,
        actor: str = "system",
    ) -> RecoveryCase:
        """Create a new recovery case linked to a revenue record."""
        # Ensure revenue record exists
        RevenueService.get_revenue_record_by_id(db, case_in.revenue_record_id)

        recovery_case = RecoveryCase(
            revenue_record_id=case_in.revenue_record_id,
            reason=case_in.reason,
            risk_status=case_in.risk_status,
            priority=case_in.priority,
            current_state=case_in.current_state,
        )
        db.add(recovery_case)
        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(recovery_case.id),
            action="recovery_case_created",
            actor=actor,
            metadata={
                "revenue_record_id": recovery_case.revenue_record_id,
                "reason": recovery_case.reason,
                "risk_status": recovery_case.risk_status.value,
                "priority": recovery_case.priority.value,
                "current_state": recovery_case.current_state.value,
            },
        )
        db.commit()
        db.refresh(recovery_case)
        return recovery_case

    @staticmethod
    def get_recovery_case_by_id(db: Session, case_id: int) -> RecoveryCase:
        """Fetch a recovery case by ID with preloaded actions or raise NotFoundError."""
        query = (
            select(RecoveryCase)
            .options(selectinload(RecoveryCase.actions))
            .where(RecoveryCase.id == case_id)
        )
        case = db.scalar(query)
        if case is None:
            raise NotFoundError(f"RecoveryCase with id {case_id} not found")
        return case

    @staticmethod
    def list_recovery_cases(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        state: Optional[RecoveryCaseState] = None,
        priority: Optional[RecoveryPriority] = None,
    ) -> tuple[list[RecoveryCase], int]:
        """List recovery cases with optional filtering and pagination."""
        query = select(RecoveryCase).options(selectinload(RecoveryCase.actions))
        count_query = select(func.count()).select_from(RecoveryCase)

        if state is not None:
            query = query.where(RecoveryCase.current_state == state)
            count_query = count_query.where(RecoveryCase.current_state == state)
        if priority is not None:
            query = query.where(RecoveryCase.priority == priority)
            count_query = count_query.where(RecoveryCase.priority == priority)

        total = db.scalar(count_query) or 0
        items = list(
            db.scalars(
                query.order_by(RecoveryCase.created_at.desc())
                .offset(skip)
                .limit(limit)
            ).all()
        )
        return items, total

    @staticmethod
    def update_recovery_case_state(
        db: Session,
        case_id: int,
        state_update: RecoveryCaseStateUpdate,
        actor: str = "system",
    ) -> RecoveryCase:
        """
        Transition recovery case state validating against the deterministic state machine.
        Raises InvalidStateTransitionError on invalid transition attempts.
        """
        case = RecoveryService.get_recovery_case_by_id(db, case_id)
        current_state = case.current_state
        target_state = state_update.current_state

        allowed_targets = ALLOWED_STATE_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_targets:
            raise InvalidStateTransitionError(
                current_state=current_state.value,
                target_state=target_state.value,
            )

        case.current_state = target_state
        if state_update.reason is not None:
            case.reason = state_update.reason

        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(case.id),
            action="recovery_case_state_updated",
            actor=actor,
            metadata={
                "from_state": current_state.value,
                "to_state": target_state.value,
                "reason": case.reason,
            },
        )
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def create_recovery_action(
        db: Session,
        case_id: int,
        action_in: RecoveryActionCreate,
        actor: str = "system",
    ) -> RecoveryAction:
        """Create a new recovery intervention action under a case."""
        case = RecoveryService.get_recovery_case_by_id(db, case_id)

        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=action_in.action_type,
            channel=action_in.channel,
            status=action_in.status,
            scheduled_at=action_in.scheduled_at,
            executed_at=action_in.executed_at,
            result=action_in.result,
        )
        db.add(action)
        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_action",
            entity_id=str(action.id),
            action="recovery_action_created",
            actor=actor,
            metadata={
                "recovery_case_id": case.id,
                "action_type": action.action_type.value,
                "channel": action.channel.value,
                "status": action.status.value,
            },
        )
        db.commit()
        db.refresh(action)
        return action

    @staticmethod
    def update_recovery_action_status(
        db: Session,
        action_id: int,
        status_update: RecoveryActionStatusUpdate,
        actor: str = "system",
    ) -> RecoveryAction:
        """Update recovery action status, execution timestamp, and results."""
        action = db.scalar(
            select(RecoveryAction).where(RecoveryAction.id == action_id)
        )
        if action is None:
            raise NotFoundError(f"RecoveryAction with id {action_id} not found")

        old_status = action.status
        action.status = status_update.status

        if status_update.result is not None:
            action.result = status_update.result

        if status_update.executed_at is not None:
            action.executed_at = status_update.executed_at
        elif (
            status_update.status == RecoveryActionStatus.executed
            and action.executed_at is None
        ):
            action.executed_at = datetime.now(timezone.utc)

        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_action",
            entity_id=str(action.id),
            action="recovery_action_status_updated",
            actor=actor,
            metadata={
                "recovery_case_id": action.recovery_case_id,
                "from_status": old_status.value,
                "to_status": action.status.value,
                "executed_at": (
                    action.executed_at.isoformat() if action.executed_at else None
                ),
            },
        )
        db.commit()
        db.refresh(action)
        return action
