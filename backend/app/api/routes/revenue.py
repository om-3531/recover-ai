"""
Revenue REST API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.revenue import (
    RevenueRecordCreate,
    RevenueRecordResponse,
    RevenueStatusUpdate,
)
from app.services.revenue_service import RevenueService

router = APIRouter(prefix="/revenue", tags=["revenue"])


@router.post(
    "",
    response_model=RevenueRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a revenue record",
)
def create_revenue(
    revenue_in: RevenueRecordCreate,
    db: Session = Depends(get_db),
) -> RevenueRecordResponse:
    """Create a new 1:1 revenue record linked to a payment."""
    record = RevenueService.create_revenue_record(db=db, revenue_in=revenue_in)
    return RevenueRecordResponse.model_validate(record)


@router.get(
    "/{revenue_id}",
    response_model=RevenueRecordResponse,
    summary="Get revenue record by ID",
)
def get_revenue(
    revenue_id: int,
    db: Session = Depends(get_db),
) -> RevenueRecordResponse:
    """Fetch a revenue record by primary key."""
    record = RevenueService.get_revenue_record_by_id(db=db, revenue_id=revenue_id)
    return RevenueRecordResponse.model_validate(record)


@router.get(
    "/payment/{payment_id}",
    response_model=RevenueRecordResponse,
    summary="Get revenue record by payment ID",
)
def get_revenue_by_payment(
    payment_id: int,
    db: Session = Depends(get_db),
) -> RevenueRecordResponse:
    """Fetch the revenue record linked 1:1 to a specific payment."""
    record = RevenueService.get_revenue_record_by_payment_id(
        db=db, payment_id=payment_id
    )
    return RevenueRecordResponse.model_validate(record)


@router.patch(
    "/{revenue_id}/status",
    response_model=RevenueRecordResponse,
    summary="Update revenue status",
)
def update_revenue_status(
    revenue_id: int,
    status_update: RevenueStatusUpdate,
    db: Session = Depends(get_db),
) -> RevenueRecordResponse:
    """Update status and recoverable amount for a revenue record."""
    record = RevenueService.update_revenue_status(
        db=db, revenue_id=revenue_id, status_update=status_update
    )
    return RevenueRecordResponse.model_validate(record)


@router.post(
    "/{revenue_id}/mark-at-risk",
    response_model=RevenueRecordResponse,
    summary="Mark revenue as at-risk",
)
def mark_revenue_at_risk(
    revenue_id: int,
    recoverable_amount: Optional[int] = Query(
        None, description="Optional override for recoverable amount in paise"
    ),
    db: Session = Depends(get_db),
) -> RevenueRecordResponse:
    """Deterministically mark a revenue record as at-risk."""
    record = RevenueService.mark_revenue_at_risk(
        db=db, revenue_id=revenue_id, recoverable_amount=recoverable_amount
    )
    return RevenueRecordResponse.model_validate(record)
