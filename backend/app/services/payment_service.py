"""
PaymentService business logic.

Manages payment records, status updates, idempotency checks, and audit trails.
Operates on internal database records only; does NOT execute external Razorpay API calls.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.schemas.payments import PaymentCreate
from app.services.audit_service import AuditService


class PaymentService:
    """Service for managing payment domain entities."""

    @staticmethod
    def create_payment(
        db: Session,
        payment_in: PaymentCreate,
        actor: str = "system",
    ) -> Payment:
        """
        Create a new payment record and emit an audit log entry.
        Raises ConflictError if razorpay_payment_id already exists.
        """
        existing = db.scalar(
            select(Payment).where(Payment.razorpay_payment_id == payment_in.razorpay_payment_id)
        )
        if existing is not None:
            raise ConflictError(
                f"Payment with razorpay_payment_id '{payment_in.razorpay_payment_id}' already exists"
            )

        payment = Payment(
            razorpay_payment_id=payment_in.razorpay_payment_id,
            razorpay_order_id=payment_in.razorpay_order_id,
            amount=payment_in.amount,
            currency=payment_in.currency,
            status=payment_in.status,
            method=payment_in.method,
            customer_email=str(payment_in.customer_email) if payment_in.customer_email else None,
            customer_reference=payment_in.customer_reference,
        )
        db.add(payment)
        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="payment",
            entity_id=str(payment.id),
            action="payment_created",
            actor=actor,
            metadata={
                "razorpay_payment_id": payment.razorpay_payment_id,
                "amount": payment.amount,
                "currency": payment.currency,
                "status": payment.status.value,
            },
        )
        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def get_payment_by_id(db: Session, payment_id: int) -> Payment:
        """Fetch a payment by its internal ID or raise NotFoundError."""
        payment = db.scalar(select(Payment).where(Payment.id == payment_id))
        if payment is None:
            raise NotFoundError(f"Payment with id {payment_id} not found")
        return payment

    @staticmethod
    def get_payment_by_razorpay_id(db: Session, razorpay_payment_id: str) -> Payment:
        """Fetch a payment by its Razorpay identifier or raise NotFoundError."""
        payment = db.scalar(
            select(Payment).where(Payment.razorpay_payment_id == razorpay_payment_id)
        )
        if payment is None:
            raise NotFoundError(
                f"Payment with razorpay_payment_id '{razorpay_payment_id}' not found"
            )
        return payment

    @staticmethod
    def list_payments(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        status: Optional[PaymentStatus] = None,
    ) -> tuple[list[Payment], int]:
        """List payments with optional status filtering and pagination."""
        query = select(Payment)
        count_query = select(func.count()).select_from(Payment)

        if status is not None:
            query = query.where(Payment.status == status)
            count_query = count_query.where(Payment.status == status)

        total = db.scalar(count_query) or 0
        items = list(
            db.scalars(
                query.order_by(Payment.created_at.desc())
                .offset(skip)
                .limit(limit)
            ).all()
        )
        return items, total

    @staticmethod
    def update_payment_status(
        db: Session,
        payment_id: int,
        new_status: PaymentStatus,
        actor: str = "system",
    ) -> Payment:
        """Update payment status and record audit log."""
        payment = PaymentService.get_payment_by_id(db, payment_id)
        old_status = payment.status
        payment.status = new_status
        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="payment",
            entity_id=str(payment.id),
            action="payment_status_updated",
            actor=actor,
            metadata={
                "from_status": old_status.value,
                "to_status": new_status.value,
            },
        )
        db.commit()
        db.refresh(payment)
        return payment
