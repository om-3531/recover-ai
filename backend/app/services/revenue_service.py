"""
RevenueService business logic.

Manages financial tracking, gross and recoverable amount calculations,
revenue-at-risk identification, and 1:1 payment linkages.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import RevenueStatus
from app.models.revenue import RevenueRecord
from app.schemas.revenue import RevenueRecordCreate, RevenueStatusUpdate
from app.services.audit_service import AuditService
from app.services.payment_service import PaymentService


class RevenueService:
    """Service for managing revenue records and risk identification."""

    @staticmethod
    def create_revenue_record(
        db: Session,
        revenue_in: RevenueRecordCreate,
        actor: str = "system",
    ) -> RevenueRecord:
        """
        Create a RevenueRecord linked 1:1 to a Payment.
        Validates payment existence and enforces single revenue record per payment.
        """
        payment = PaymentService.get_payment_by_id(db, revenue_in.payment_id)

        existing = db.scalar(
            select(RevenueRecord).where(RevenueRecord.payment_id == revenue_in.payment_id)
        )
        if existing is not None:
            raise ConflictError(
                f"RevenueRecord for payment_id {revenue_in.payment_id} already exists"
            )

        gross_amount = (
            revenue_in.gross_amount
            if revenue_in.gross_amount is not None
            else payment.amount
        )

        if revenue_in.recoverable_amount is not None:
            recoverable_amount = revenue_in.recoverable_amount
        elif revenue_in.status == RevenueStatus.at_risk:
            recoverable_amount = gross_amount
        else:
            recoverable_amount = 0

        revenue_record = RevenueRecord(
            payment_id=payment.id,
            gross_amount=gross_amount,
            recoverable_amount=recoverable_amount,
            currency=revenue_in.currency or payment.currency,
            status=revenue_in.status,
        )
        db.add(revenue_record)
        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="revenue_record",
            entity_id=str(revenue_record.id),
            action="revenue_created",
            actor=actor,
            metadata={
                "payment_id": payment.id,
                "gross_amount": gross_amount,
                "recoverable_amount": recoverable_amount,
                "status": revenue_record.status.value,
            },
        )
        db.commit()
        db.refresh(revenue_record)
        return revenue_record

    @staticmethod
    def get_revenue_record_by_id(db: Session, revenue_id: int) -> RevenueRecord:
        """Fetch a revenue record by internal ID or raise NotFoundError."""
        record = db.scalar(
            select(RevenueRecord).where(RevenueRecord.id == revenue_id)
        )
        if record is None:
            raise NotFoundError(f"RevenueRecord with id {revenue_id} not found")
        return record

    @staticmethod
    def get_revenue_record_by_payment_id(db: Session, payment_id: int) -> RevenueRecord:
        """Fetch a revenue record linked to a payment or raise NotFoundError."""
        record = db.scalar(
            select(RevenueRecord).where(RevenueRecord.payment_id == payment_id)
        )
        if record is None:
            raise NotFoundError(f"RevenueRecord for payment_id {payment_id} not found")
        return record

    @staticmethod
    def update_revenue_status(
        db: Session,
        revenue_id: int,
        status_update: RevenueStatusUpdate,
        actor: str = "system",
    ) -> RevenueRecord:
        """Update status and optionally recoverable amount on a revenue record."""
        record = RevenueService.get_revenue_record_by_id(db, revenue_id)
        old_status = record.status
        record.status = status_update.status

        if status_update.recoverable_amount is not None:
            record.recoverable_amount = status_update.recoverable_amount
        elif status_update.status == RevenueStatus.at_risk and record.recoverable_amount == 0:
            record.recoverable_amount = record.gross_amount

        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="revenue_record",
            entity_id=str(record.id),
            action="revenue_status_updated",
            actor=actor,
            metadata={
                "from_status": old_status.value,
                "to_status": record.status.value,
                "recoverable_amount": record.recoverable_amount,
            },
        )
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def mark_revenue_at_risk(
        db: Session,
        revenue_id: int,
        recoverable_amount: Optional[int] = None,
        actor: str = "system",
    ) -> RevenueRecord:
        """Deterministically mark a revenue record as at-risk."""
        record = RevenueService.get_revenue_record_by_id(db, revenue_id)
        old_status = record.status
        record.status = RevenueStatus.at_risk

        if recoverable_amount is not None:
            record.recoverable_amount = recoverable_amount
        else:
            record.recoverable_amount = record.gross_amount

        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="revenue_record",
            entity_id=str(record.id),
            action="revenue_marked_at_risk",
            actor=actor,
            metadata={
                "from_status": old_status.value,
                "to_status": RevenueStatus.at_risk.value,
                "recoverable_amount": record.recoverable_amount,
            },
        )
        db.commit()
        db.refresh(record)
        return record
