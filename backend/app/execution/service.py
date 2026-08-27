"""
RecoveryExecutionService business logic.

Manages authorized recovery action execution, channel adapters, idempotency guards,
case state machine synchronization, and audit logging.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.approval.policy import _ensure_utc
from app.core.metrics import metrics
from app.execution.exceptions import ExecutionAuthorizationError
from app.execution.executor import RecoveryExecutor
from app.execution.mock_executor import MockRecoveryExecutor
from app.execution.schemas import ExecutionResponse, ExecutionResult

from app.models.approval import RecoveryApproval
from app.models.enums import (
    ApprovalStatus,
    JobStatus,
    RecoveryActionStatus,
    RecoveryCaseState,
)
from app.models.job import RecoveryExecutionJob
from app.models.recovery import RecoveryAction, RecoveryCase

from app.models.revenue import RevenueRecord
from app.schemas.recovery import RecoveryCaseStateUpdate
from app.services.audit_service import AuditService
from app.services.recovery_service import RecoveryService


class RecoveryExecutionService:
    """Service for executing approved recovery actions idempotently and safely."""

    @staticmethod
    def execute_approval(
        db: Session,
        approval_id: int,
        executor: Optional[RecoveryExecutor] = None,
        actor: str = "system",
    ) -> ExecutionResponse:
        """
        Execute an approved recovery intervention.

        Enforces:
        1. Explicit server-side approval authorization (rejects pending/rejected/expired).
        2. Strict idempotency: returns existing result if already executed.
        3. RecoveryCase state machine transition synchronization.
        4. Audit trail logging for all execution events.
        """
        # Step 1: Load approval and linked models
        query = (
            select(RecoveryApproval)
            .options(
                selectinload(RecoveryApproval.recovery_action),
                selectinload(RecoveryApproval.recovery_case).selectinload(
                    RecoveryCase.revenue_record
                ),
            )
            .where(RecoveryApproval.id == approval_id)
        )
        approval = db.scalar(query)
        if approval is None:
            raise ExecutionAuthorizationError(
                f"Recovery approval with id {approval_id} not found"
            )

        case: RecoveryCase = approval.recovery_case

        # Step 2: Verify approval status & expiration
        now = datetime.now(timezone.utc)
        if approval.expires_at and _ensure_utc(approval.expires_at) < now:
            approval.status = ApprovalStatus.expired
            db.commit()
            raise ExecutionAuthorizationError("Cannot execute expired approval")

        if approval.status == ApprovalStatus.pending:
            raise ExecutionAuthorizationError(
                "Cannot execute pending approval. Explicit approval authorization is required."
            )

        if approval.status in (ApprovalStatus.rejected, ApprovalStatus.cancelled):
            raise ExecutionAuthorizationError(
                f"Cannot execute approval with '{approval.status.value}' status"
            )

        if approval.status != ApprovalStatus.approved:
            raise ExecutionAuthorizationError(
                f"Approval status is '{approval.status.value}'. Execution requires 'approved' status."
            )

        # Step 3: Verify case is not terminal
        if case.current_state in (
            RecoveryCaseState.recovered,
            RecoveryCaseState.closed,
        ):
            raise ExecutionAuthorizationError(
                f"Cannot execute action on case in terminal state '{case.current_state.value}'"
            )

        # Step 4: Idempotency Check — if already executed, return cached result
        if approval.recovery_action_id is not None:
            existing_action = approval.recovery_action
            if (
                existing_action
                and existing_action.status == RecoveryActionStatus.executed
                and approval.execution_result
            ):
                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_approval",
                    entity_id=str(approval.id),
                    action="execution_duplicate_ignored",
                    actor=actor,
                    metadata={
                        "approval_id": approval.id,
                        "recovery_action_id": existing_action.id,
                    },
                )
                db.commit()
                return ExecutionResponse(
                    approval_id=approval.id,
                    recovery_case_id=case.id,
                    recovery_action_id=existing_action.id,
                    result=ExecutionResult.model_validate(approval.execution_result),
                    case_state=case.current_state,
                )

        # Step 5: Audit execution start
        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_approval",
            entity_id=str(approval.id),
            action="execution_requested",
            actor=actor,
            metadata={
                "action_type": approval.action_type.value,
                "channel": approval.channel.value,
            },
        )

        # Step 6: Create RecoveryAction record and bind to approval
        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=approval.action_type,
            channel=approval.channel,
            status=RecoveryActionStatus.pending,
            scheduled_at=now,
        )
        db.add(action)
        db.flush()
        approval.recovery_action_id = action.id

        # Step 7: Execute using execution adapter
        exec_adapter = executor or MockRecoveryExecutor()
        context = {
            "recovery_case_id": case.id,
            "revenue_record_id": case.revenue_record_id,
            "payment_id": (
                case.revenue_record.payment_id if case.revenue_record else None
            ),
        }
        exec_result = exec_adapter.execute(
            action_type=approval.action_type,
            channel=approval.channel,
            context=context,
        )

        # Step 8: Persist execution result on RecoveryAction, Approval, & ExecutionJob
        action.status = exec_result.status
        action.result = exec_result.model_dump(mode="json")
        action.executed_at = exec_result.executed_at
        approval.execution_result = exec_result.model_dump(mode="json")

        job_key = f"approval:{approval.id}:case:{case.id}:action:{approval.action_type.value}:{approval.channel.value}"
        existing_job = db.scalar(
            select(RecoveryExecutionJob).where(
                RecoveryExecutionJob.idempotency_key == job_key
            )
        )
        if not existing_job:
            job = RecoveryExecutionJob(
                recovery_case_id=case.id,
                recovery_approval_id=approval.id,
                recovery_action_id=action.id,
                status=JobStatus.succeeded if exec_result.success else JobStatus.failed,
                attempt_count=1,
                max_attempts=3,
                idempotency_key=job_key,
                scheduled_at=action.scheduled_at or now,
                started_at=now,
                completed_at=exec_result.executed_at,
                error_code=exec_result.error_code,
                error_message=exec_result.message if not exec_result.success else None,
                result=action.result,
            )
            db.add(job)
        else:
            existing_job.status = (
                JobStatus.succeeded if exec_result.success else JobStatus.failed
            )
            existing_job.completed_at = exec_result.executed_at
            existing_job.result = action.result
            existing_job.recovery_action_id = action.id

        # Step 10: State machine transition synchronization
        if exec_result.success:
            metrics.increment("execution_successes_total")
            if case.current_state == RecoveryCaseState.open:
                RecoveryService.update_recovery_case_state(
                    db=db,
                    case_id=case.id,
                    state_update=RecoveryCaseStateUpdate(
                        current_state=RecoveryCaseState.action_pending,
                        reason="Action approved and scheduled",
                    ),
                    actor=actor,
                )
                RecoveryService.update_recovery_case_state(
                    db=db,
                    case_id=case.id,
                    state_update=RecoveryCaseStateUpdate(
                        current_state=RecoveryCaseState.recovering,
                        reason=f"Action executed via {approval.channel.value}",
                    ),
                    actor=actor,
                )
            elif case.current_state == RecoveryCaseState.action_pending:
                RecoveryService.update_recovery_case_state(
                    db=db,
                    case_id=case.id,
                    state_update=RecoveryCaseStateUpdate(
                        current_state=RecoveryCaseState.recovering,
                        reason=f"Action executed via {approval.channel.value}",
                    ),
                    actor=actor,
                )

            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_action",
                entity_id=str(action.id),
                action="execution_succeeded",
                actor=actor,
                metadata={
                    "execution_id": exec_result.execution_id,
                    "channel": approval.channel.value,
                    "action_type": approval.action_type.value,
                },
            )
        else:
            metrics.increment("execution_failures_total")
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_action",
                entity_id=str(action.id),

                action="execution_failed",
                actor=actor,
                metadata={
                    "execution_id": exec_result.execution_id,
                    "error_code": exec_result.error_code,
                    "retryable": exec_result.retryable,
                },
            )

        db.commit()
        db.refresh(approval)
        db.refresh(action)
        db.refresh(case)

        return ExecutionResponse(
            approval_id=approval.id,
            recovery_case_id=case.id,
            recovery_action_id=action.id,
            result=exec_result,
            case_state=case.current_state,
        )
