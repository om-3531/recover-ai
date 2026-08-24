"""
Razorpay Service layer.

Coordinates Razorpay operations, signature verification, and audit logging.
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.razorpay.client import RazorpayClient
from app.integrations.razorpay.exceptions import (
    RazorpayConfigurationError,
    RazorpaySignatureVerificationError,
)
from app.integrations.razorpay.signature import (
    verify_payment_signature as _verify_payment_signature,
    verify_webhook_signature as _verify_webhook_signature,
)
from app.schemas.orders import RazorpayOrderCreate
from app.services.audit_service import AuditService


class RazorpayService:
    """Application-level service for Razorpay operations."""

    @staticmethod
    def create_order(
        db: Session,
        order_in: RazorpayOrderCreate,
        client: Optional[RazorpayClient] = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        """Create a Razorpay order and record an audit log entry."""
        razorpay_client = client or RazorpayClient()
        order_data = razorpay_client.create_order(
            amount=order_in.amount,
            currency=order_in.currency,
            receipt=order_in.receipt,
            notes=order_in.notes,
        )

        AuditService.create_audit_log(
            db=db,
            entity_type="razorpay_order",
            entity_id=order_data.get("id", "unknown"),
            action="razorpay_order_created",
            actor=actor,
            metadata={
                "amount": order_in.amount,
                "currency": order_in.currency,
                "status": order_data.get("status", "created"),
            },
        )
        db.commit()
        return order_data

    @staticmethod
    def verify_payment_signature(
        db: Session,
        order_id: str,
        payment_id: str,
        signature: str,
        secret: Optional[str] = None,
        actor: str = "system",
    ) -> bool:
        """
        Verify payment signature received after customer checkout.
        Raises RazorpaySignatureVerificationError on invalid signature.
        """
        settings = get_settings()
        key_secret = secret or settings.RAZORPAY_KEY_SECRET
        if not key_secret:
            raise RazorpayConfigurationError("RAZORPAY_KEY_SECRET is not configured")

        is_valid = _verify_payment_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            secret=key_secret,
        )

        if not is_valid:
            AuditService.create_audit_log(
                db=db,
                entity_type="payment",
                entity_id=payment_id,
                action="payment_signature_rejected",
                actor=actor,
                metadata={"order_id": order_id},
            )
            db.commit()
            raise RazorpaySignatureVerificationError(
                "Invalid Razorpay signature"
            )

        AuditService.create_audit_log(
            db=db,
            entity_type="payment",
            entity_id=payment_id,
            action="payment_signature_verified",
            actor=actor,
            metadata={"order_id": order_id},
        )
        db.commit()
        return True

    @staticmethod
    def verify_webhook_signature(
        raw_body: bytes,
        signature: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify webhook signature using the configured webhook secret."""
        settings = get_settings()
        webhook_secret = secret or settings.RAZORPAY_WEBHOOK_SECRET
        if not webhook_secret:
            raise RazorpayConfigurationError("RAZORPAY_WEBHOOK_SECRET is not configured")

        return _verify_webhook_signature(
            raw_body=raw_body,
            signature=signature,
            secret=webhook_secret,
        )
