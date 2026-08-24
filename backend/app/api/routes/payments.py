"""
Payment REST API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import PaymentStatus
from app.schemas.payments import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentStatusUpdate,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a payment record",
)
def create_payment(
    payment_in: PaymentCreate,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Create a new internal payment transaction record."""
    payment = PaymentService.create_payment(db=db, payment_in=payment_in)
    return PaymentResponse.model_validate(payment)


@router.get(
    "",
    response_model=PaymentListResponse,
    summary="List payments",
)
def list_payments(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit for pagination"),
    payment_status: Optional[PaymentStatus] = Query(None, alias="status", description="Filter by status"),
    db: Session = Depends(get_db),
) -> PaymentListResponse:
    """List payment records with optional status filtering and pagination."""
    items, total = PaymentService.list_payments(
        db=db, skip=skip, limit=limit, status=payment_status
    )
    return PaymentListResponse(
        items=[PaymentResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment by internal ID",
)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Fetch a single payment by its primary key."""
    payment = PaymentService.get_payment_by_id(db=db, payment_id=payment_id)
    return PaymentResponse.model_validate(payment)


@router.get(
    "/razorpay/{razorpay_payment_id}",
    response_model=PaymentResponse,
    summary="Get payment by Razorpay payment ID",
)
def get_payment_by_razorpay_id(
    razorpay_payment_id: str,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Fetch a single payment by its unique Razorpay payment identifier."""
    payment = PaymentService.get_payment_by_razorpay_id(
        db=db, razorpay_payment_id=razorpay_payment_id
    )
    return PaymentResponse.model_validate(payment)


@router.patch(
    "/{payment_id}/status",
    response_model=PaymentResponse,
    summary="Update payment status",
)
def update_payment_status(
    payment_id: int,
    status_update: PaymentStatusUpdate,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Update a payment's status and record audit log."""
    payment = PaymentService.update_payment_status(
        db=db, payment_id=payment_id, new_status=status_update.status
    )
    return PaymentResponse.model_validate(payment)
