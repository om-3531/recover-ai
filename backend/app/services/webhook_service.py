"""
WebhookService business logic.

Processes inbound Razorpay webhooks with signature verification,
idempotent deduplication, payment/revenue state transitions,
automatic RecoveryCase creation, orchestration, and audit logging.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.metrics import metrics
from app.integrations.razorpay.exceptions import RazorpaySignatureVerificationError
from app.integrations.razorpay.service import RazorpayService
from app.models.enums import (
    PaymentEventProcessingStatus,
    PaymentMethod,
    PaymentStatus,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueStatus,
    RiskStatus,
)
from app.models.payment import Payment, PaymentEvent
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.schemas.recovery import RecoveryCaseCreate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Risk thresholds for automatic risk assessment on webhook ingestion
_LOW_RISK_MAX_AMOUNT = 100000      # < ₹1,000
_MEDIUM_RISK_MAX_AMOUNT = 1000000  # < ₹10,000
_HIGH_RISK_MAX_AMOUNT = 5000000    # < ₹50,000
# >= ₹50,000 is critical risk



class WebhookService:
    """Service for ingesting and processing Razorpay webhooks idempotently."""

    @staticmethod
    def _parse_payment_method(method_str: Optional[str]) -> Optional[PaymentMethod]:
        """Safely parse method string to PaymentMethod enum."""
        if not method_str:
            return None
        try:
            return PaymentMethod(method_str.lower())
        except ValueError:
            return PaymentMethod.other

    @staticmethod
    def _assess_risk_from_amount(amount_paise: int) -> tuple[RiskStatus, RecoveryPriority]:
        """Assess risk level and priority from payment amount in paise."""
        if amount_paise >= _HIGH_RISK_MAX_AMOUNT:
            return RiskStatus.critical, RecoveryPriority.urgent
        elif amount_paise >= _MEDIUM_RISK_MAX_AMOUNT:
            return RiskStatus.high, RecoveryPriority.high
        elif amount_paise >= _LOW_RISK_MAX_AMOUNT:
            return RiskStatus.medium, RecoveryPriority.medium
        else:
            return RiskStatus.low, RecoveryPriority.medium

    @classmethod
    def process_razorpay_webhook(
        cls,
        db: Session,
        raw_body: bytes,
        signature: str,
        webhook_secret: Optional[str] = None,
        event_id_header: Optional[str] = None,
        actor: str = "razorpay_webhook",
    ) -> dict[str, Any]:
        """
        Ingest, verify, and process a Razorpay webhook payload.

        Steps:
        1. Verify HMAC SHA-256 signature using webhook secret.
        2. Parse JSON payload and extract event ID.
        3. Check idempotency: if event already exists, return duplicate success.
        4. Create PaymentEvent record in database.
        5. Map event to Payment and RevenueRecord models.
        6. Emit comprehensive audit trail.
        """
        metrics.increment("webhook_received_total")

        # Step 1: Verify HMAC signature
        is_valid = RazorpayService.verify_webhook_signature(
            raw_body=raw_body,
            signature=signature,
            secret=webhook_secret,
        )
        if not is_valid:
            metrics.increment("webhook_failed_total")
            raise RazorpaySignatureVerificationError("Invalid Razorpay webhook signature")

        # Step 2: Parse JSON payload
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Payload must be a JSON object")
        except Exception as exc:
            metrics.increment("webhook_failed_total")
            raise BadRequestError("Malformed JSON payload in webhook") from exc

        # Step 3: Extract Event ID and Event Type
        event_id = payload.get("id") or payload.get("event_id") or event_id_header
        if not event_id:
            metrics.increment("webhook_failed_total")
            raise BadRequestError("Missing event ID in webhook payload")

        event_type = payload.get("event", "unknown")

        # Step 4: Idempotency Check
        existing_event = db.scalar(
            select(PaymentEvent).where(PaymentEvent.razorpay_event_id == event_id)
        )
        if existing_event is not None:
            metrics.increment("webhook_duplicate_total")
            AuditService.create_audit_log(
                db=db,
                entity_type="payment_event",
                entity_id=str(existing_event.id),
                action="razorpay_webhook_duplicate",
                actor=actor,
                metadata={
                    "event_id": event_id,
                    "event_type": event_type,
                    "message": "Duplicate event ignored",
                },
            )
            db.commit()
            return {
                "status": "duplicate",
                "event_id": event_id,
                "event_type": event_type,
                "message": "Duplicate event ignored",
            }


        # Step 5: Create PaymentEvent record
        payment_event = PaymentEvent(
            razorpay_event_id=event_id,
            event_type=event_type,
            payload=payload,
            processing_status=PaymentEventProcessingStatus.pending,
            received_at=datetime.now(timezone.utc),
        )
        db.add(payment_event)
        db.flush()

        AuditService.create_audit_log(
            db=db,
            entity_type="payment_event",
            entity_id=str(payment_event.id),
            action="razorpay_webhook_received",
            actor=actor,
            metadata={"event_id": event_id, "event_type": event_type},
        )

        # Step 6: Process business state transitions
        payment_entity = (
            payload.get("payload", {}).get("payment", {}).get("entity", {})
        )
        payment_id_rzp = payment_entity.get("id")

        # Initialize orchestration return values (only set for payment.failed)
        recovery_case_id = None
        orchestration_status = None
        orchestration_message = None
        approval_id = None
        payment = None

        if payment_id_rzp:
            # Find or create Payment record
            payment = db.scalar(
                select(Payment).where(Payment.razorpay_payment_id == payment_id_rzp)
            )
            amount = payment_entity.get("amount", 0)
            currency = payment_entity.get("currency", "INR")
            order_id = payment_entity.get("order_id")
            method = cls._parse_payment_method(payment_entity.get("method"))
            email = payment_entity.get("email")
            contact = payment_entity.get("contact") or payment_entity.get("customer_id")

            if payment is None:
                initial_status = (
                    PaymentStatus.captured
                    if event_type == "payment.captured"
                    else (
                        PaymentStatus.failed
                        if event_type == "payment.failed"
                        else PaymentStatus.created
                    )
                )
                payment = Payment(
                    razorpay_payment_id=payment_id_rzp,
                    razorpay_order_id=order_id,
                    amount=amount,
                    currency=currency,
                    status=initial_status,
                    method=method,
                    customer_email=email,
                    customer_reference=contact,
                )
                db.add(payment)
                db.flush()
            else:
                # Update existing payment fields
                if order_id and not payment.razorpay_order_id:
                    payment.razorpay_order_id = order_id
                if amount and payment.amount == 0:
                    payment.amount = amount
                if method and not payment.method:
                    payment.method = method
                if email and not payment.customer_email:
                    payment.customer_email = email
                if contact and not payment.customer_reference:
                    payment.customer_reference = contact

            payment_event.payment_id = payment.id

            # Apply state transitions for supported events
            if event_type == "payment.captured":
                payment.status = PaymentStatus.captured
                db.flush()

                # Synchronize RevenueRecord
                revenue = db.scalar(
                    select(RevenueRecord).where(RevenueRecord.payment_id == payment.id)
                )
                if revenue is None:
                    revenue = RevenueRecord(
                        payment_id=payment.id,
                        gross_amount=payment.amount,
                        recoverable_amount=0,
                        currency=payment.currency,
                        status=RevenueStatus.recognized,
                    )
                    db.add(revenue)
                else:
                    if revenue.status == RevenueStatus.at_risk:
                        revenue.status = RevenueStatus.recovered
                    else:
                        revenue.status = RevenueStatus.recognized
                    revenue.recoverable_amount = 0

                AuditService.create_audit_log(
                    db=db,
                    entity_type="payment",
                    entity_id=str(payment.id),
                    action="payment_captured",
                    actor=actor,
                    metadata={"razorpay_payment_id": payment_id_rzp, "amount": payment.amount},
                )

            elif event_type == "payment.failed":
                payment.status = PaymentStatus.failed
                db.flush()

                # Synchronize RevenueRecord as at-risk
                revenue = db.scalar(
                    select(RevenueRecord).where(RevenueRecord.payment_id == payment.id)
                )
                if revenue is None:
                    revenue = RevenueRecord(
                        payment_id=payment.id,
                        gross_amount=payment.amount,
                        recoverable_amount=payment.amount,
                        currency=payment.currency,
                        status=RevenueStatus.at_risk,
                    )
                    db.add(revenue)
                else:
                    revenue.status = RevenueStatus.at_risk
                    revenue.recoverable_amount = revenue.gross_amount

                db.flush()

                AuditService.create_audit_log(
                    db=db,
                    entity_type="payment",
                    entity_id=str(payment.id),
                    action="payment_failed",
                    actor=actor,
                    metadata={"razorpay_payment_id": payment_id_rzp, "amount": payment.amount},
                )

                # Auto-create RecoveryCase and trigger orchestration
                try:
                    # Risk assessment from payment amount
                    risk_status, priority = WebhookService._assess_risk_from_amount(payment.amount)

                    # Determine reason from error details
                    error_reason = payment_entity.get("error_reason") or payment_entity.get("error_code") or "payment_failed"
                    error_description = payment_entity.get("error_description", "")

                    # Check if recovery case already exists for this revenue record
                    existing_case = db.scalar(
                        select(RecoveryCase).where(RecoveryCase.revenue_record_id == revenue.id)
                    )

                    if existing_case is None:
                        # Create RecoveryCase
                        recovery_case = RecoveryCase(
                            revenue_record_id=revenue.id,
                            reason=error_reason,
                            risk_status=risk_status,
                            priority=priority,
                            current_state=RecoveryCaseState.open,
                        )
                        db.add(recovery_case)
                        db.flush()

                        recovery_case_id = recovery_case.id

                        AuditService.create_audit_log(
                            db=db,
                            entity_type="recovery_case",
                            entity_id=str(recovery_case.id),
                            action="recovery_case_created_from_webhook",
                            actor=actor,
                            metadata={
                                "payment_id": payment.id,
                                "revenue_record_id": revenue.id,
                                "amount": payment.amount,
                                "risk_status": risk_status.value,
                                "priority": priority.value,
                                "reason": error_reason,
                            },
                        )

                        # Trigger orchestration (AI → Policy → Approval → Execution)
                        try:
                            from app.orchestration.orchestrator import RecoveryOrchestrator

                            orchestration_result = RecoveryOrchestrator.orchestrate_recovery(
                                db=db,
                                case_id=recovery_case.id,
                                ai_provider=None,  # Use default provider
                                actor="webhook_auto_orchestration",
                            )
                            orchestration_status = orchestration_result.status.value
                            orchestration_message = orchestration_result.message
                            approval_id = orchestration_result.approval_id

                            AuditService.create_audit_log(
                                db=db,
                                entity_type="recovery_case",
                                entity_id=str(recovery_case.id),
                                action="webhook_orchestration_completed",
                                actor=actor,
                                metadata={
                                    "orchestration_status": orchestration_status,
                                    "approval_id": approval_id,
                                    "message": orchestration_message,
                                },
                            )
                        except Exception as orch_exc:
                            logger.warning(
                                "Orchestration failed for case %s: %s",
                                recovery_case.id,
                                orch_exc,
                            )
                            orchestration_status = "orchestration_error"
                            orchestration_message = f"Orchestration failed: {type(orch_exc).__name__}"

                            AuditService.create_audit_log(
                                db=db,
                                entity_type="recovery_case",
                                entity_id=str(recovery_case.id),
                                action="webhook_orchestration_failed",
                                actor=actor,
                                metadata={
                                    "error": type(orch_exc).__name__,
                                    "message": str(orch_exc)[:200],
                                },
                            )
                    else:
                        recovery_case_id = existing_case.id
                        orchestration_status = "case_already_exists"
                        orchestration_message = f"Recovery case {existing_case.id} already exists for this revenue record"

                except Exception as case_exc:
                    logger.warning(
                        "Failed to create recovery case for payment %s: %s",
                        payment.id,
                        case_exc,
                    )
                    AuditService.create_audit_log(
                        db=db,
                        entity_type="payment",
                        entity_id=str(payment.id),
                        action="recovery_case_creation_failed",
                        actor=actor,
                        metadata={
                            "error": type(case_exc).__name__,
                            "message": str(case_exc)[:200],
                        },
                    )

            else:
                # Unsupported event for a known payment
                AuditService.create_audit_log(
                    db=db,
                    entity_type="payment_event",
                    entity_id=str(payment_event.id),
                    action="razorpay_webhook_unsupported",
                    actor=actor,
                    metadata={"event_type": event_type},
                )
        else:
            # Event without payment payload entity
            AuditService.create_audit_log(
                db=db,
                entity_type="payment_event",
                entity_id=str(payment_event.id),
                action="razorpay_webhook_unsupported",
                actor=actor,
                metadata={"event_type": event_type},
            )

        # Step 7: Finalize PaymentEvent
        payment_event.processing_status = PaymentEventProcessingStatus.processed
        payment_event.processed_at = datetime.now(timezone.utc)
        metrics.increment("webhook_processed_total")

        AuditService.create_audit_log(
            db=db,
            entity_type="payment_event",
            entity_id=str(payment_event.id),
            action="razorpay_webhook_processed",
            actor=actor,
            metadata={
                "event_id": event_id,
                "event_type": event_type,
                "payment_id": payment.id if payment else None,
                "recovery_case_id": recovery_case_id,
                "orchestration_status": orchestration_status,
                "orchestration_message": orchestration_message,
                "message": "Webhook processed successfully",
            },
        )

        db.commit()
        db.refresh(payment_event)

        return {
            "status": "processed",
            "event_id": event_id,
            "event_type": event_type,
            "message": "Webhook processed successfully",
            "recovery_case_id": recovery_case_id,
            "orchestration_status": orchestration_status,
            "orchestration_message": orchestration_message,
            "approval_id": approval_id,
        }

