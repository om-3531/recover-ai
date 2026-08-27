"""
ApprovalService business logic.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.approval.exceptions import ApprovalNotFoundError
from app.approval.policy import ApprovalPolicy, _ensure_utc
from app.approval.schemas import ApprovalCreateRequest, ApprovalDecisionRequest
from app.core.metrics import metrics
from app.models.approval import RecoveryApproval
from app.models.enums import ApprovalStatus
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.services.audit_service import AuditService



class ApprovalService:
    """Service for managing recovery approval requests and decision lifecycles."""

    @staticmethod
    def create_approval(
        db: Session,
        request: ApprovalCreateRequest,
        actor: str = "system",
    ) -> RecoveryApproval:
        """Create a new pending recovery approval request for an AI recommendation."""
        # 1. Fetch case with relations
        case = db.scalar(
            select(RecoveryCase)
            .options(
                selectinload(RecoveryCase.revenue_record).selectinload(
                    RevenueRecord.payment
                )
            )
            .where(RecoveryCase.id == request.recovery_case_id)
        )
        if case is None:
            raise ApprovalNotFoundError(
                f"RecoveryCase with id {request.recovery_case_id} not found"
            )

        # 2. Validate creation policy
        ApprovalPolicy.validate_approval_creation(case)

        # 3. Create approval record
        now = datetime.now(timezone.utc)
        expires_at = (
            now + timedelta(hours=request.expires_in_hours)
            if request.expires_in_hours
            else None
        )

        approval = RecoveryApproval(
            recovery_case_id=case.id,
            action_type=request.action_type,
            channel=request.channel,
            recommendation_id=request.recommendation_id,
            status=ApprovalStatus.pending,
            requires_human_review=request.requires_human_review,
            requested_at=now,
            expires_at=expires_at,
        )
        db.add(approval)
        db.flush()

        metrics.increment("approval_requests_total")

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_approval",
            entity_id=str(approval.id),
            action="approval_requested",
            actor=actor,
            metadata={
                "recovery_case_id": case.id,
                "action_type": approval.action_type.value,
                "channel": approval.channel.value,
                "requires_human_review": approval.requires_human_review,
                "recommendation_id": approval.recommendation_id,
            },
        )
        db.commit()
        db.refresh(approval)
        return approval

    @staticmethod
    def get_approval_by_id(db: Session, approval_id: int) -> RecoveryApproval:
        """Fetch approval record by ID and evaluate expiration."""
        approval = db.scalar(
            select(RecoveryApproval)
            .options(selectinload(RecoveryApproval.recovery_case))
            .where(RecoveryApproval.id == approval_id)
        )
        if approval is None:
            raise ApprovalNotFoundError(
                f"Recovery approval with id {approval_id} not found"
            )

        # Check expiration
        now = datetime.now(timezone.utc)
        if (
            approval.status == ApprovalStatus.pending
            and approval.expires_at
            and _ensure_utc(approval.expires_at) < now
        ):
            approval.status = ApprovalStatus.expired
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_approval",
                entity_id=str(approval.id),
                action="approval_expired",
                actor="system",
                metadata={"expired_at": approval.expires_at.isoformat()},
            )
            db.commit()
            db.refresh(approval)

        return approval

    @staticmethod
    def approve_approval(
        db: Session,
        approval_id: int,
        decision: Optional[ApprovalDecisionRequest] = None,
        actor: str = "system",
    ) -> RecoveryApproval:
        """Approve a pending recovery approval request."""
        approval = ApprovalService.get_approval_by_id(db, approval_id)
        ApprovalPolicy.validate_approval_decision(approval, "approve")

        approver = decision.approved_by if decision and decision.approved_by else actor
        now = datetime.now(timezone.utc)

        approval.status = ApprovalStatus.approved
        approval.approved_by = approver
        approval.approved_at = now

        metrics.increment("approvals_total")

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_approval",
            entity_id=str(approval.id),
            action="approval_approved",
            actor=approver,
            metadata={
                "recovery_case_id": approval.recovery_case_id,
                "action_type": approval.action_type.value,
                "channel": approval.channel.value,
            },
        )
        db.commit()
        db.refresh(approval)
        return approval

    @staticmethod
    def reject_approval(
        db: Session,
        approval_id: int,
        decision: Optional[ApprovalDecisionRequest] = None,
        actor: str = "system",
    ) -> RecoveryApproval:
        """Reject a pending recovery approval request."""
        approval = ApprovalService.get_approval_by_id(db, approval_id)
        ApprovalPolicy.validate_approval_decision(approval, "reject")

        rejector = decision.approved_by if decision and decision.approved_by else actor
        rejection_reason = (
            decision.rejection_reason
            if decision and decision.rejection_reason
            else "Rejected by operator"
        )
        now = datetime.now(timezone.utc)

        approval.status = ApprovalStatus.rejected
        approval.rejection_reason = rejection_reason
        approval.rejected_at = now

        metrics.increment("rejections_total")

        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_approval",
            entity_id=str(approval.id),
            action="approval_rejected",
            actor=rejector,
            metadata={
                "recovery_case_id": approval.recovery_case_id,
                "rejection_reason": rejection_reason,
            },
        )

        db.commit()
        db.refresh(approval)
        return approval

    @staticmethod
    def list_approvals(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        status: Optional[ApprovalStatus] = None,
        recovery_case_id: Optional[int] = None,
    ) -> tuple[list[RecoveryApproval], int]:
        """List recovery approvals with optional filtering and pagination."""
        query = select(RecoveryApproval).options(
            selectinload(RecoveryApproval.recovery_case)
        )
        count_query = select(func.count()).select_from(RecoveryApproval)

        if status is not None:
            query = query.where(RecoveryApproval.status == status)
            count_query = count_query.where(RecoveryApproval.status == status)
        if recovery_case_id is not None:
            query = query.where(
                RecoveryApproval.recovery_case_id == recovery_case_id
            )
            count_query = count_query.where(
                RecoveryApproval.recovery_case_id == recovery_case_id
            )

        total = db.scalar(count_query) or 0
        items = list(
            db.scalars(
                query.order_by(RecoveryApproval.created_at.desc())
                .offset(skip)
                .limit(limit)
            ).all()
        )
        return items, total
