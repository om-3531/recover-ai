"""
AI Decision Engine REST API routes.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.ai.decision_engine import RecoveryDecisionEngine
from app.ai.schemas import RecoveryRecommendation
from app.db.session import get_db

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/recovery-cases/{case_id}/decision",
    response_model=RecoveryRecommendation,
    status_code=status.HTTP_200_OK,
    summary="Generate AI recovery recommendation",
)
def generate_recovery_decision(
    case_id: int,
    db: Session = Depends(get_db),
) -> RecoveryRecommendation:
    """
    Generate a structured, policy-checked recovery recommendation for an active recovery case.

    Advisory only: does not execute financial transactions or mutate case state directly.
    """
    return RecoveryDecisionEngine.generate_decision(db=db, case_id=case_id)
