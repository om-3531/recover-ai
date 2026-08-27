"""
Recovery Approval and Execution REST API routes.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.approval.schemas import (
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ApprovalListResponse,
    ApprovalResponse,
)
from app.approval.service import ApprovalService
from app.db.session import get_db
from app.execution.schemas import ExecutionResponse
from app.execution.service import RecoveryExecutionService
from app.models.enums import ApprovalStatus

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recovery action approval request",
)
def create_approval_request(
    request: ApprovalCreateRequest,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Create an authoritative approval request for an AI recovery recommendation."""
    approval = ApprovalService.create_approval(db=db, request=request)
    return ApprovalResponse.model_validate(approval)


@router.get(
    "",
    response_model=ApprovalListResponse,
    summary="List recovery approvals",
)
def list_approvals(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit for pagination"),
    approval_status: Optional[ApprovalStatus] = Query(
        None, alias="status", description="Filter by approval status"
    ),
    recovery_case_id: Optional[int] = Query(
        None, description="Filter by RecoveryCase ID"
    ),
    db: Session = Depends(get_db),
) -> ApprovalListResponse:
    """List recovery approvals with optional status and case filtering."""
    items, total = ApprovalService.list_approvals(
        db=db,
        skip=skip,
        limit=limit,
        status=approval_status,
        recovery_case_id=recovery_case_id,
    )
    return ApprovalListResponse(
        items=[ApprovalResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    summary="Get approval details",
)
def get_approval(
    approval_id: int,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Fetch approval details by ID with expiration evaluation."""
    approval = ApprovalService.get_approval_by_id(db=db, approval_id=approval_id)
    return ApprovalResponse.model_validate(approval)


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a pending recovery action",
)
def approve_recovery_action(
    approval_id: int,
    decision: Optional[ApprovalDecisionRequest] = Body(default=None),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Explicitly authorize execution of a pending recovery action."""
    approval = ApprovalService.approve_approval(
        db=db, approval_id=approval_id, decision=decision
    )
    return ApprovalResponse.model_validate(approval)


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject a pending recovery action",
)
def reject_recovery_action(
    approval_id: int,
    decision: Optional[ApprovalDecisionRequest] = Body(default=None),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Reject a pending recovery approval request."""
    approval = ApprovalService.reject_approval(
        db=db, approval_id=approval_id, decision=decision
    )
    return ApprovalResponse.model_validate(approval)


@router.post(
    "/{approval_id}/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute an approved recovery action",
)
def execute_approved_recovery_action(
    approval_id: int,
    db: Session = Depends(get_db),
) -> ExecutionResponse:
    """
    Execute an approved recovery action across its assigned channel.

    Enforces:
    - Server-side 'approved' authorization gate.
    - Strict execution idempotency.
    - RecoveryCase state machine synchronization.
    """
    return RecoveryExecutionService.execute_approval(db=db, approval_id=approval_id)
