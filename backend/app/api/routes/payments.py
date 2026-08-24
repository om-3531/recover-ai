"""
Payment REST API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.razorpay.service import RazorpayService
from app.models.enums import PaymentStatus
from app.schemas.orders import (
    PaymentSignatureVerifyRequest,
    PaymentSignatureVerifyResponse,
    RazorpayOrderCreate,
    RazorpayOrderResponse,
)
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


@router.post(
    "/orders",
    response_model=RazorpayOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Razorpay order",
)
def create_razorpay_order(
    order_in: RazorpayOrderCreate,
    db: Session = Depends(get_db),
) -> RazorpayOrderResponse:
    """
    Create an order in Razorpay using the isolated integration layer.
    Amounts must be integers in paise (e.g. 49900 = 499.00 INR).
    """
    order_data = RazorpayService.create_order(db=db, order_in=order_in)
    return RazorpayOrderResponse(
        id=order_data["id"],
        amount=order_data["amount"],
        currency=order_data["currency"],
        status=order_data.get("status", "created"),
        receipt=order_data.get("receipt"),
        created_at=order_data.get("created_at"),
    )


@router.post(
    "/verify-signature",
    response_model=PaymentSignatureVerifyResponse,
    summary="Verify checkout payment signature",
)
def verify_payment_signature(
    verify_in: PaymentSignatureVerifyRequest,
    db: Session = Depends(get_db),
) -> PaymentSignatureVerifyResponse:
    """
    Verify customer checkout signature according to Razorpay HMAC-SHA256 mechanism.
    Rejects invalid signatures with HTTP 400 Bad Request.
    """
    RazorpayService.verify_payment_signature(
        db=db,
        order_id=verify_in.razorpay_order_id,
        payment_id=verify_in.razorpay_payment_id,
        signature=verify_in.razorpay_signature,
    )
    return PaymentSignatureVerifyResponse(
        verified=True,
        message="Payment signature verified successfully",
    )


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
