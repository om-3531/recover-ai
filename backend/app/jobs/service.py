"""
JobService business logic.

Coordinates persistent background execution jobs, bounded retries, provider dispatch,
idempotency guarantees, and RecoveryCase state machine synchronization.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.approval.policy import _ensure_utc
from app.core.metrics import metrics
from app.execution.exceptions import ExecutionAuthorizationError
from app.jobs.exceptions import JobNotFoundError
from app.models.approval import RecoveryApproval

from app.models.enums import (
    ApprovalStatus,
    JobStatus,
    RecoveryActionStatus,
    RecoveryCaseState,
)
from app.models.job import RecoveryExecutionJob
from app.models.payment import Payment
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord
from app.providers.base import ProviderContext, ProviderResult
from app.providers.registry import (
    ProviderRegistry,
    get_default_provider_registry,
)
from app.schemas.recovery import RecoveryCaseStateUpdate
from app.services.audit_service import AuditService
from app.services.recovery_service import RecoveryService


class JobService:
    """Service for managing the asynchronous lifecycle of recovery execution jobs."""

    @classmethod
    def create_job(
        cls,
        db: Session,
        approval_id: int,
        max_attempts: int = 3,
        idempotency_key: Optional[str] = None,
        auto_process: bool = True,
        registry: Optional[ProviderRegistry] = None,
        actor: str = "system",
    ) -> RecoveryExecutionJob:
        """
        Create and optionally dispatch a background execution job for an approved action.

        Guarantees:
        1. Explicit server-side approval authorization (status == approved).
        2. Unexpired approval.
        3. Non-terminal RecoveryCase.
        4. Idempotency uniqueness based on deterministically computed key.
        5. Audit logging for execution_queued.
        """
        query = (
            select(RecoveryApproval)
            .options(
                selectinload(RecoveryApproval.recovery_action),
                selectinload(RecoveryApproval.recovery_case).selectinload(
                    RecoveryCase.revenue_record
                ).selectinload(RevenueRecord.payment),
            )
            .where(RecoveryApproval.id == approval_id)
        )
        approval = db.scalar(query)
        if approval is None:
            raise JobNotFoundError(
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

        # Step 4: Deterministic Idempotency Key
        key = idempotency_key or (
            f"approval:{approval.id}:case:{case.id}:action:{approval.action_type.value}:{approval.channel.value}"
        )

        # Step 5: Idempotency Check
        existing_job = db.scalar(
            select(RecoveryExecutionJob).where(
                RecoveryExecutionJob.idempotency_key == key
            )
        )
        if existing_job:
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_execution_job",
                entity_id=str(existing_job.id),
                action="execution_duplicate_ignored",
                actor=actor,
                metadata={
                    "approval_id": approval.id,
                    "existing_job_id": existing_job.id,
                    "status": existing_job.status.value,
                },
            )
            db.commit()
            return existing_job

        # Step 6: Create Queued Job
        job = RecoveryExecutionJob(
            recovery_case_id=case.id,
            recovery_approval_id=approval.id,
            recovery_action_id=approval.recovery_action_id,
            status=JobStatus.queued,
            attempt_count=0,
            max_attempts=max_attempts,
            idempotency_key=key,
            scheduled_at=now,
        )
        db.add(job)
        db.flush()

        metrics.increment("execution_jobs_total")

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_execution_job",
            entity_id=str(job.id),
            action="execution_queued",
            actor=actor,
            metadata={
                "approval_id": approval.id,
                "action_type": approval.action_type.value,
                "channel": approval.channel.value,
            },
        )

        db.commit()
        db.refresh(job)

        # Step 7: Auto Process if requested
        if auto_process:
            return cls.process_job(
                db=db,
                job_id=job.id,
                registry=registry,
                actor=actor,
            )

        return job

    @classmethod
    def process_job(
        cls,
        db: Session,
        job_id: int,
        registry: Optional[ProviderRegistry] = None,
        actor: str = "system",
    ) -> RecoveryExecutionJob:
        """
        Process a queued or retry-scheduled execution job.

        Executes provider dispatch, updates attempt counts, handles bounded retries,
        updates RecoveryAction result, advances RecoveryCase state machine, and logs audit events.
        """
        query = (
            select(RecoveryExecutionJob)
            .options(
                selectinload(RecoveryExecutionJob.recovery_approval).selectinload(
                    RecoveryApproval.recovery_action
                ),
                selectinload(RecoveryExecutionJob.recovery_case).selectinload(
                    RecoveryCase.revenue_record
                ).selectinload(RevenueRecord.payment),
            )
            .where(RecoveryExecutionJob.id == job_id)
        )
        job = db.scalar(query)
        if job is None:
            raise JobNotFoundError(f"RecoveryExecutionJob with id {job_id} not found")

        # Idempotency guard: do not re-process succeeded or cancelled jobs
        if job.status == JobStatus.succeeded:
            return job

        approval: RecoveryApproval = job.recovery_approval
        case: RecoveryCase = job.recovery_case

        # Update Job to Running
        now = datetime.now(timezone.utc)
        job.status = JobStatus.running
        job.started_at = now
        job.attempt_count += 1
        db.commit()

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_execution_job",
            entity_id=str(job.id),
            action="execution_started",
            actor=actor,
            metadata={"attempt_count": job.attempt_count},
        )

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_execution_job",
            entity_id=str(job.id),
            action="provider_dispatch_started",
            actor=actor,
            metadata={
                "channel": approval.channel.value,
                "action_type": approval.action_type.value,
            },
        )

        # Build Provider Context
        payment: Optional[Payment] = (
            case.revenue_record.payment if case.revenue_record else None
        )
        context = ProviderContext(
            recovery_case_id=case.id,
            revenue_record_id=case.revenue_record_id,
            payment_id=payment.id if payment else None,
            customer_email=payment.customer_email if payment else None,
            customer_phone=payment.customer_reference if payment else None,
            amount=(
                case.revenue_record.recoverable_amount
                if case.revenue_record
                else None
            ),
            currency=case.revenue_record.currency if case.revenue_record else "INR",
            action_type=approval.action_type,
            channel=approval.channel,
        )

        # Dispatch via Provider Registry
        prov_reg = registry or get_default_provider_registry()
        provider = prov_reg.get_provider(approval.channel)
        metrics.increment("provider_dispatches_total")
        provider_result: ProviderResult = provider.send(context)

        # Handle Provider Result
        if provider_result.success:
            metrics.increment("execution_successes_total")
            job.status = JobStatus.succeeded
            job.completed_at = datetime.now(timezone.utc)
            job.result = provider_result.model_dump(mode="json")
            job.error_code = None
            job.error_message = None

            # Create or update RecoveryAction
            if approval.recovery_action_id is None:
                action = RecoveryAction(
                    recovery_case_id=case.id,
                    action_type=approval.action_type,
                    channel=approval.channel,
                    status=RecoveryActionStatus.executed,
                    scheduled_at=job.scheduled_at,
                    executed_at=job.completed_at,
                    result=job.result,
                )
                db.add(action)
                db.flush()
                approval.recovery_action_id = action.id
                job.recovery_action_id = action.id
            else:
                action = approval.recovery_action
                action.status = RecoveryActionStatus.executed
                action.executed_at = job.completed_at
                action.result = job.result
                job.recovery_action_id = action.id

            approval.execution_result = job.result

            # Synchronize RecoveryCase State
            if case.current_state == RecoveryCaseState.open:
                RecoveryService.update_recovery_case_state(
                    db=db,
                    case_id=case.id,
                    state_update=RecoveryCaseStateUpdate(
                        current_state=RecoveryCaseState.action_pending,
                        reason="Action approved and job running",
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

            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_execution_job",
                entity_id=str(job.id),
                action="provider_dispatch_succeeded",
                actor=actor,
                metadata={
                    "provider_message_id": provider_result.provider_message_id,
                },
            )
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_execution_job",
                entity_id=str(job.id),
                action="execution_succeeded",
                actor=actor,
                metadata={"job_id": job.id},
            )
        else:
            metrics.increment("provider_failures_total")
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_execution_job",
                entity_id=str(job.id),
                action="provider_dispatch_failed",
                actor=actor,
                metadata={
                    "error_code": provider_result.error_code,
                    "retryable": provider_result.retryable,
                },
            )

            # Bounded Retry Check
            if provider_result.retryable and job.attempt_count < job.max_attempts:
                metrics.increment("retry_scheduled_jobs_total")
                job.status = JobStatus.retry_scheduled
                backoff_seconds = (2 ** job.attempt_count) * 10
                job.next_retry_at = datetime.now(timezone.utc) + timedelta(
                    seconds=backoff_seconds
                )
                job.error_code = provider_result.error_code
                job.error_message = provider_result.error_message
                job.result = provider_result.model_dump(mode="json")

                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_execution_job",
                    entity_id=str(job.id),
                    action="execution_retry_scheduled",
                    actor=actor,
                    metadata={
                        "next_retry_at": job.next_retry_at.isoformat(),
                        "attempt_count": job.attempt_count,
                    },
                )
            else:
                metrics.increment("execution_failures_total")
                job.status = JobStatus.failed
                job.completed_at = datetime.now(timezone.utc)
                job.error_code = provider_result.error_code
                job.error_message = provider_result.error_message
                job.result = provider_result.model_dump(mode="json")


                # Update RecoveryAction to failed
                if approval.recovery_action_id is None:
                    action = RecoveryAction(
                        recovery_case_id=case.id,
                        action_type=approval.action_type,
                        channel=approval.channel,
                        status=RecoveryActionStatus.failed,
                        scheduled_at=job.scheduled_at,
                        executed_at=job.completed_at,
                        result=job.result,
                    )
                    db.add(action)
                    db.flush()
                    approval.recovery_action_id = action.id
                    job.recovery_action_id = action.id
                else:
                    action = approval.recovery_action
                    action.status = RecoveryActionStatus.failed
                    action.result = job.result
                    job.recovery_action_id = action.id

                approval.execution_result = job.result

                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_execution_job",
                    entity_id=str(job.id),
                    action="execution_failed",
                    actor=actor,
                    metadata={
                        "error_code": job.error_code,
                        "attempt_count": job.attempt_count,
                    },
                )

        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def get_job(cls, db: Session, job_id: int) -> RecoveryExecutionJob:
        """Fetch a specific execution job by ID."""
        job = db.scalar(
            select(RecoveryExecutionJob).where(RecoveryExecutionJob.id == job_id)
        )
        if job is None:
            raise JobNotFoundError(f"Execution job with id {job_id} not found")
        return job

    @classmethod
    def list_jobs(
        cls,
        db: Session,
        case_id: Optional[int] = None,
        approval_id: Optional[int] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RecoveryExecutionJob], int]:
        """Fetch paginated execution jobs with optional filtering."""
        query = select(RecoveryExecutionJob)
        count_query = select(func.count(RecoveryExecutionJob.id))

        if case_id is not None:
            query = query.where(RecoveryExecutionJob.recovery_case_id == case_id)
            count_query = count_query.where(
                RecoveryExecutionJob.recovery_case_id == case_id
            )

        if approval_id is not None:
            query = query.where(
                RecoveryExecutionJob.recovery_approval_id == approval_id
            )
            count_query = count_query.where(
                RecoveryExecutionJob.recovery_approval_id == approval_id
            )

        if status is not None:
            query = query.where(RecoveryExecutionJob.status == status)
            count_query = count_query.where(
                RecoveryExecutionJob.status == status
            )

        total = db.scalar(count_query) or 0
        items = (
            db.scalars(
                query.order_by(RecoveryExecutionJob.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .all()
        )
        return list(items), total
