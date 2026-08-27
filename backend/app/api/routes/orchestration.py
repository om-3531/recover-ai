"""
Recovery Orchestration REST API routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.orchestration.orchestrator import RecoveryOrchestrator
from app.orchestration.schemas import (
    OrchestrateRequest,
    OrchestrationResult,
    WorkflowStatusResponse,
)

router = APIRouter(tags=["orchestration"])


@router.post(
    "/recovery-cases/{case_id}/orchestrate",
    response_model=OrchestrationResult,
    status_code=status.HTTP_200_OK,
    summary="Orchestrate recovery workflow for a recovery case",
)
@router.post(
    "/recovery/cases/{case_id}/orchestrate",
    response_model=OrchestrationResult,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def orchestrate_recovery_case(
    case_id: int,
    request: Optional[OrchestrateRequest] = None,
    db: Session = Depends(get_db),
) -> OrchestrationResult:
    """
    Orchestrate an end-to-end recovery workflow for a given recovery case.

    Guarantees:
    1. Evaluates case validity and terminal state protections.
    2. Enforces idempotency (reuses existing approvals/executions).
    3. Generates AI recommendation through PolicyEngine.
    4. Creates authoritative RecoveryApproval record.
    5. Stops at human review for high/critical risk cases.
    6. Authorizes and executes action only when policy permits.
    7. Records audit logs for all workflow transitions.

    The auto_execute_low_risk setting is loaded from the merchant policy
    in the database. If explicitly provided in the request body, it overrides
    the policy value for this specific orchestration.
    """
    auto_execute = request.auto_execute_low_risk if request else None
    return RecoveryOrchestrator.orchestrate_recovery(
        db=db,
        case_id=case_id,
        auto_execute_low_risk=auto_execute,
    )


@router.get(
    "/recovery-cases/{case_id}/workflow",
    response_model=WorkflowStatusResponse,
    summary="Get recovery case workflow diagnostic status",
)
@router.get(
    "/recovery/cases/{case_id}/workflow",
    response_model=WorkflowStatusResponse,
    include_in_schema=False,
)
def get_recovery_case_workflow(
    case_id: int,
    db: Session = Depends(get_db),
) -> WorkflowStatusResponse:
    """Retrieve the current orchestration workflow lifecycle status for a recovery case."""
    return RecoveryOrchestrator.get_workflow_status(db=db, case_id=case_id)
