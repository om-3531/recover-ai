"""
RecoveryOrchestrator application coordination service.

Connects RecoveryCase, RecoveryDecisionEngine, PolicyEngine, ApprovalService,
and RecoveryExecutionService into a safe, idempotent, and policy-governed workflow.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.decision_engine import RecoveryDecisionEngine
from app.ai.provider import AIProvider
from app.ai.schemas import RecoveryRecommendation
from app.approval.schemas import ApprovalCreateRequest, ApprovalDecisionRequest
from app.approval.service import ApprovalService
from app.core.exceptions import NotFoundError
from app.core.metrics import metrics
from app.execution.executor import RecoveryExecutor
from app.execution.schemas import ExecutionResult

from app.execution.service import RecoveryExecutionService
from app.models.approval import RecoveryApproval
from app.models.enums import (
    ApprovalStatus,
    RecoveryActionStatus,
    RecoveryCaseState,
    RiskStatus,
)
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord
from app.orchestration.schemas import (
    OrchestrationResult,
    WorkflowStatus,
    WorkflowStatusResponse,
)
from app.policy.schemas import MerchantPolicyBase
from app.policy.service import PolicyService
from app.services.audit_service import AuditService


class RecoveryOrchestrator:
    """
    Coordinates end-to-end recovery workflows with deterministic policy gates.

    Strict Architectural Boundaries:
    1. AI never directly authorizes or executes actions.
    2. Every intervention produces an authoritative RecoveryApproval record.
    3. High/critical risk cases strictly stop at 'approval_required'.
    4. Execution is idempotent and synchronizes RecoveryCase state.
    """

    @classmethod
    def orchestrate_recovery(
        cls,
        db: Session,
        case_id: int,
        auto_execute_low_risk: Optional[bool] = None,
        ai_provider: Optional[AIProvider] = None,
        executor: Optional[RecoveryExecutor] = None,
        actor: str = "recovery_orchestrator",
    ) -> OrchestrationResult:
        """
        Orchestrate the complete recovery workflow for a given case.

        Sequence:
        1. Case & Terminal State Validation
        2. Idempotency Check (returns existing approval/execution if present)
        3. AI Recommendation & Policy Evaluation
        4. Approval Creation (via ApprovalService)
        5. Human-in-the-Loop Safeguard (stops if high risk or review required)
        6. Authorized Execution (via RecoveryExecutionService)
        7. Audit Logging & State Synchronization

        The auto_execute_low_risk parameter defaults to the merchant policy setting
        from the database. If explicitly provided, it overrides the policy value.
        """
        # Load merchant policy from DB for authoritative settings
        merchant_policy_orm = PolicyService.get_or_create_default_policy(db)
        merchant_policy = MerchantPolicyBase(
            high_risk_threshold_paise=merchant_policy_orm.high_risk_threshold_paise,
            critical_risk_threshold_paise=merchant_policy_orm.critical_risk_threshold_paise,
            human_review_threshold_paise=merchant_policy_orm.human_review_threshold_paise,
            auto_execute_low_risk=merchant_policy_orm.auto_execute_low_risk,
            max_attempts=merchant_policy_orm.max_attempts,
            backoff_base_seconds=merchant_policy_orm.backoff_base_seconds,
            allowed_channels=merchant_policy_orm.allowed_channels,
            preferred_channel=merchant_policy_orm.preferred_channel,
            min_recovery_amount_paise=merchant_policy_orm.min_recovery_amount_paise,
            max_recovery_amount_paise=merchant_policy_orm.max_recovery_amount_paise,
            require_approval_for_high_risk=merchant_policy_orm.require_approval_for_high_risk,
            require_approval_for_critical_risk=merchant_policy_orm.require_approval_for_critical_risk,
            webhook_enabled=merchant_policy_orm.webhook_enabled,
            is_active=merchant_policy_orm.is_active,
        )

        # Use explicit parameter if provided, otherwise use merchant policy setting
        effective_auto_execute = auto_execute_low_risk if auto_execute_low_risk is not None else merchant_policy.auto_execute_low_risk

        # Step 1: Fetch RecoveryCase with relations
        query = (
            select(RecoveryCase)
            .options(
                selectinload(RecoveryCase.actions),
                selectinload(RecoveryCase.approvals).selectinload(
                    RecoveryApproval.recovery_action
                ),
                selectinload(RecoveryCase.revenue_record).selectinload(
                    RevenueRecord.payment
                ),
            )
            .where(RecoveryCase.id == case_id)
        )
        case = db.scalar(query)
        if case is None:
            raise NotFoundError(f"RecoveryCase with id {case_id} not found")

        # Audit workflow start
        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(case.id),
            action="orchestration_started",
            actor=actor,
            metadata={
                "auto_execute_low_risk": effective_auto_execute,
                "policy_source": "merchant_policy_db",
                "merchant_id": merchant_policy_orm.merchant_id,
            },
        )

        # Terminal case validation
        if case.current_state in (
            RecoveryCaseState.recovered,
            RecoveryCaseState.closed,
        ):
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_case",
                entity_id=str(case.id),
                action="orchestration_policy_blocked",
                actor=actor,
                metadata={"reason": f"Terminal state: {case.current_state.value}"},
            )
            db.commit()
            return OrchestrationResult(
                recovery_case_id=case.id,
                status=WorkflowStatus.policy_blocked,
                case_state=case.current_state,
                is_blocked=True,
                message=f"Case is in terminal state '{case.current_state.value}'",
                next_action="None (Case Resolved)",
            )

        # Zero recoverable balance validation
        if case.revenue_record and case.revenue_record.recoverable_amount <= 0:
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_case",
                entity_id=str(case.id),
                action="orchestration_policy_blocked",
                actor=actor,
                metadata={"reason": "Recoverable amount is 0 paise"},
            )
            db.commit()
            return OrchestrationResult(
                recovery_case_id=case.id,
                status=WorkflowStatus.policy_blocked,
                case_state=case.current_state,
                is_blocked=True,
                message="Recoverable amount is 0 paise",
                next_action="None (Zero Balance)",
            )

        # Step 2: Idempotency Protection
        for existing_appr in reversed(case.approvals):
            # If an approval was already executed
            if (
                existing_appr.status == ApprovalStatus.approved
                and existing_appr.execution_result
            ):
                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_case",
                    entity_id=str(case.id),
                    action="orchestration_duplicate_ignored",
                    actor=actor,
                    metadata={"existing_approval_id": existing_appr.id},
                )
                db.commit()
                return OrchestrationResult(
                    recovery_case_id=case.id,
                    status=WorkflowStatus.completed,
                    case_state=case.current_state,
                    approval_id=existing_appr.id,
                    execution_result=ExecutionResult.model_validate(
                        existing_appr.execution_result
                    ),
                    message="Recovery action already executed for this case",
                    next_action="Monitor for payment recovery event",
                )

            # If an approval is already pending review
            if existing_appr.status == ApprovalStatus.pending:
                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_case",
                    entity_id=str(case.id),
                    action="orchestration_duplicate_ignored",
                    actor=actor,
                    metadata={"pending_approval_id": existing_appr.id},
                )
                db.commit()
                return OrchestrationResult(
                    recovery_case_id=case.id,
                    status=WorkflowStatus.approval_required,
                    case_state=case.current_state,
                    approval_id=existing_appr.id,
                    requires_human_review=existing_appr.requires_human_review,
                    message="Pending approval already exists for this case",
                    next_action=f"Authorize via POST /api/v1/approvals/{existing_appr.id}/approve",
                )

        # Step 3: Generate AI Recommendation & Evaluate Policy
        rec: RecoveryRecommendation = RecoveryDecisionEngine.generate_decision(
            db=db,
            case_id=case.id,
            provider=ai_provider,
            actor=actor,
        )

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(case.id),
            action="orchestration_recommendation_generated",
            actor=actor,
            metadata={"recommendation_id": rec.recommendation_id},
        )

        # If policy blocked the recommendation
        if rec.is_blocked or rec.recommended_action_type is None:
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_case",
                entity_id=str(case.id),
                action="orchestration_policy_blocked",
                actor=actor,
                metadata={"reason": rec.rationale},
            )
            db.commit()
            return OrchestrationResult(
                recovery_case_id=case.id,
                status=WorkflowStatus.policy_blocked,
                case_state=case.current_state,
                recommendation=rec,
                is_blocked=True,
                message=rec.rationale or "Intervention blocked by policy",
                next_action="Review policy block reason",
            )

        # Step 4: Create Authoritative Approval Record
        approval = ApprovalService.create_approval(
            db=db,
            request=ApprovalCreateRequest(
                recovery_case_id=case.id,
                action_type=rec.recommended_action_type,
                channel=rec.recommended_channel,
                recommendation_id=rec.recommendation_id,
                requires_human_review=rec.requires_human_review,
            ),
            actor=actor,
        )

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(case.id),
            action="orchestration_approval_created",
            actor=actor,
            metadata={"approval_id": approval.id},
        )

        # Step 5: Human-in-the-Loop Safeguard
        is_high_risk = case.risk_status in (
            RiskStatus.high,
            RiskStatus.critical,
        )
        if rec.requires_human_review or is_high_risk:
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_case",
                entity_id=str(case.id),
                action="orchestration_approval_required",
                actor=actor,
                metadata={
                    "approval_id": approval.id,
                    "risk_status": case.risk_status.value,
                },
            )
            db.commit()
            return OrchestrationResult(
                recovery_case_id=case.id,
                status=WorkflowStatus.approval_required,
                case_state=case.current_state,
                recommendation=rec,
                approval_id=approval.id,
                requires_human_review=True,
                message="High/critical risk case requires explicit human review and approval",
                next_action=f"Authorize via POST /api/v1/approvals/{approval.id}/approve",
            )

        # Step 6: Safe Automation & Execution
        if effective_auto_execute:
            # Formally approve via ApprovalService
            ApprovalService.approve_approval(
                db=db,
                approval_id=approval.id,
                decision=ApprovalDecisionRequest(
                    approved_by="auto_policy_orchestrator"
                ),
                actor=actor,
            )

            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_case",
                entity_id=str(case.id),
                action="orchestration_execution_started",
                actor=actor,
                metadata={"approval_id": approval.id},
            )

            # Execute via RecoveryExecutionService
            exec_resp = RecoveryExecutionService.execute_approval(
                db=db,
                approval_id=approval.id,
                executor=executor,
                actor=actor,
            )

            if exec_resp.result.success:
                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_case",
                    entity_id=str(case.id),
                    action="orchestration_execution_succeeded",
                    actor=actor,
                    metadata={"execution_id": exec_resp.result.execution_id},
                )
                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_case",
                    entity_id=str(case.id),
                    action="orchestration_completed",
                    actor=actor,
                    metadata={"case_state": exec_resp.case_state.value},
                )
                metrics.increment("orchestration_completions_total")
                db.commit()
                return OrchestrationResult(
                    recovery_case_id=case.id,
                    status=WorkflowStatus.completed,
                    case_state=exec_resp.case_state,
                    recommendation=rec,
                    approval_id=approval.id,
                    execution_result=exec_resp.result,
                    message="Recovery workflow successfully executed and case transitioned to recovering",
                    next_action="Monitor for customer response / payment recovery",
                )
            else:
                metrics.increment("orchestration_failures_total")
                AuditService.create_audit_log(
                    db=db,
                    entity_type="recovery_case",
                    entity_id=str(case.id),
                    action="orchestration_execution_failed",
                    actor=actor,
                    metadata={
                        "execution_id": exec_resp.result.execution_id,
                        "retryable": exec_resp.result.retryable,
                    },
                )

                db.commit()
                return OrchestrationResult(
                    recovery_case_id=case.id,
                    status=WorkflowStatus.execution_failed,
                    case_state=exec_resp.case_state,
                    recommendation=rec,
                    approval_id=approval.id,
                    execution_result=exec_resp.result,
                    message=f"Execution failed: {exec_resp.result.message}",
                    next_action="Review error details and retry if retryable",
                )

        # If auto_execute_low_risk is False
        db.commit()
        return OrchestrationResult(
            recovery_case_id=case.id,
            status=WorkflowStatus.approval_created,
            case_state=case.current_state,
            recommendation=rec,
            approval_id=approval.id,
            requires_human_review=False,
            message="Approval created in pending status. Awaiting operator authorization.",
            next_action=f"Authorize via POST /api/v1/approvals/{approval.id}/approve",
        )

    @classmethod
    def get_workflow_status(
        cls,
        db: Session,
        case_id: int,
    ) -> WorkflowStatusResponse:
        """Derive the current diagnostic workflow state for a recovery case."""
        query = (
            select(RecoveryCase)
            .options(
                selectinload(RecoveryCase.actions),
                selectinload(RecoveryCase.approvals),
                selectinload(RecoveryCase.revenue_record),
            )
            .where(RecoveryCase.id == case_id)
        )
        case = db.scalar(query)
        if case is None:
            raise NotFoundError(f"RecoveryCase with id {case_id} not found")

        latest_approval: Optional[RecoveryApproval] = (
            case.approvals[-1] if case.approvals else None
        )
        latest_action: Optional[RecoveryAction] = (
            case.actions[-1] if case.actions else None
        )

        is_terminal = case.current_state in (
            RecoveryCaseState.recovered,
            RecoveryCaseState.closed,
        )

        # Derive workflow status
        if is_terminal:
            status = WorkflowStatus.completed if case.current_state == RecoveryCaseState.recovered else WorkflowStatus.policy_blocked
        elif latest_action and latest_action.status == RecoveryActionStatus.executed:
            status = WorkflowStatus.completed
        elif latest_action and latest_action.status == RecoveryActionStatus.failed:
            status = WorkflowStatus.execution_failed
        elif latest_approval and latest_approval.status == ApprovalStatus.approved:
            status = WorkflowStatus.approved
        elif latest_approval and latest_approval.status == ApprovalStatus.pending:
            status = WorkflowStatus.approval_required if latest_approval.requires_human_review else WorkflowStatus.approval_created
        elif latest_approval and latest_approval.status == ApprovalStatus.rejected:
            status = WorkflowStatus.policy_blocked
        else:
            status = WorkflowStatus.started

        return WorkflowStatusResponse(
            recovery_case_id=case.id,
            case_state=case.current_state,
            current_workflow_status=status,
            latest_approval_id=latest_approval.id if latest_approval else None,
            latest_approval_status=latest_approval.status if latest_approval else None,
            latest_action_id=latest_action.id if latest_action else None,
            latest_action_status=latest_action.status if latest_action else None,
            is_terminal=is_terminal,
            recoverable_amount=(
                case.revenue_record.recoverable_amount
                if case.revenue_record
                else 0
            ),
        )
