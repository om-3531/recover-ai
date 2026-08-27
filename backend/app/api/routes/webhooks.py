"""
Razorpay Webhook REST API route & Developer Simulation Console endpoints.
"""

import json
from typing import List
from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BadRequestError

from app.db.session import get_db
from app.integrations.razorpay.exceptions import RazorpaySignatureVerificationError
from app.models.audit import AuditLog
from app.integrations.razorpay.signature import create_hmac_sha256_signature
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.schemas.webhooks import (
    RazorpayConfigStatus,
    WebhookFixture,
    WebhookRecentEvent,
    WebhookRecentEventsResponse,
    WebhookResponse,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookTunnelGuide,
)
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Predefined developer fixtures
FIXTURES: List[WebhookFixture] = [
    WebhookFixture(
        key="payment_failed_insufficient_funds",
        title="Payment Failed: Insufficient Funds (Auto Recoverable)",
        event_type="payment.failed",
        description="Standard payment failure due to card balance. RecoverAI classifies as low risk and triggers automated recovery.",
        payload={
            "entity": "event",
            "account_id": "acc_demo_recoverai",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_fail_001",
                        "entity": "payment",
                        "amount": 250000,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": "order_test_001",
                        "method": "card",
                        "email": "customer1@example.com",
                        "contact": "+919876543210",
                        "error_code": "BAD_REQUEST_ERROR",
                        "error_description": "Payment failed due to insufficient funds",
                        "error_source": "bank",
                        "error_step": "payment_authorization",
                        "error_reason": "payment_failed",
                    }
                }
            },
            "created_at": 1724500000,
        },
    ),
    WebhookFixture(
        key="payment_failed_high_value",
        title="Payment Failed: High Value (> ₹10,000 Human Review)",
        event_type="payment.failed",
        description="High-value ₹45,000 transaction failure. Triggers policy human review requirement before execution.",
        payload={
            "entity": "event",
            "account_id": "acc_demo_recoverai",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_fail_high_002",
                        "entity": "payment",
                        "amount": 4500000,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": "order_test_high_002",
                        "method": "netbanking",
                        "email": "vip_client@enterprise.com",
                        "contact": "+919988776655",
                        "error_code": "GATEWAY_TIMEOUT",
                        "error_description": "Netbanking session timed out during authorization",
                        "error_source": "gateway",
                        "error_step": "payment_authorization",
                        "error_reason": "gateway_timeout",
                    }
                }
            },
            "created_at": 1724500100,
        },
    ),
    WebhookFixture(
        key="payment_captured_success",
        title="Payment Captured: Successful Recovery",
        event_type="payment.captured",
        description="Successful payment confirmation from customer recovery link, resolving revenue to recognized.",
        payload={
            "entity": "event",
            "account_id": "acc_demo_recoverai",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_cap_003",
                        "entity": "payment",
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                        "order_id": "order_test_003",
                        "method": "upi",
                        "email": "recovered_user@example.com",
                        "contact": "+919123456789",
                    }
                }
            },
            "created_at": 1724500200,
        },
    ),
    WebhookFixture(
        key="refund_created",
        title="Refund Created: Transaction Refunded",
        event_type="refund.created",
        description="A refund transaction event safely logged in the audit trail without side-effects.",
        payload={
            "entity": "event",
            "account_id": "acc_demo_recoverai",
            "event": "refund.created",
            "contains": ["refund"],
            "payload": {
                "refund": {
                    "entity": {
                        "id": "rfnd_test_004",
                        "entity": "refund",
                        "amount": 100000,
                        "currency": "INR",
                        "payment_id": "pay_test_cap_003",
                        "status": "processed",
                    }
                }
            },
            "created_at": 1724500300,
        },
    ),
]


@router.post(
    "/razorpay",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest Razorpay webhook event (Production & Tunnels)",
)
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str = Header(None, alias="X-Razorpay-Event-Id"),
    db: Session = Depends(get_db),
) -> WebhookResponse:
    """
    Receive, cryptographically verify, and process a Razorpay webhook event idempotently.
    """
    if not x_razorpay_signature:
        raise RazorpaySignatureVerificationError("Missing X-Razorpay-Signature header")

    raw_body = await request.body()

    result = WebhookService.process_razorpay_webhook(
        db=db,
        raw_body=raw_body,
        signature=x_razorpay_signature,
        event_id_header=x_razorpay_event_id,
    )
    return WebhookResponse(
        status=result["status"],
        event_id=result["event_id"],
        event_type=result.get("event_type"),
        message=result["message"],
        recovery_case_id=result.get("recovery_case_id"),
        orchestration_status=result.get("orchestration_status"),
        orchestration_message=result.get("orchestration_message"),
        approval_id=result.get("approval_id"),
    )


@router.get(
    "/config-status",
    response_model=RazorpayConfigStatus,
    summary="Get Razorpay configuration status (no secrets exposed)",
)
def get_razorpay_config_status() -> RazorpayConfigStatus:
    """Returns safe Razorpay configuration status for frontend display. Never exposes secrets."""
    app_settings = get_settings()
    key_id_present = bool(app_settings.RAZORPAY_KEY_ID)
    key_secret_present = bool(app_settings.RAZORPAY_KEY_SECRET)
    webhook_secret_present = bool(app_settings.RAZORPAY_WEBHOOK_SECRET)
    configured = key_id_present and key_secret_present and webhook_secret_present

    if configured:
        is_test = app_settings.RAZORPAY_KEY_ID.startswith("rzp_test_")
        status_msg = (
            f"Test mode active (Key: ...{app_settings.RAZORPAY_KEY_ID[-4:]})"
            if is_test
            else "Production key detected — use test mode only"
        )
    else:
        missing = []
        if not key_id_present:
            missing.append("RAZORPAY_KEY_ID")
        if not key_secret_present:
            missing.append("RAZORPAY_KEY_SECRET")
        if not webhook_secret_present:
            missing.append("RAZORPAY_WEBHOOK_SECRET")
        status_msg = f"Not configured. Missing: {', '.join(missing)}"

    return RazorpayConfigStatus(
        configured=configured,
        key_id_present=key_id_present,
        key_secret_present=key_secret_present,
        webhook_secret_present=webhook_secret_present,
        test_mode=configured and app_settings.RAZORPAY_KEY_ID.startswith("rzp_test_"),
        status_message=status_msg,
    )


@router.get(
    "/fixtures",
    response_model=List[WebhookFixture],
    summary="Get predefined synthetic webhook fixtures",
)
def get_webhook_fixtures() -> List[WebhookFixture]:
    """Returns curated synthetic Razorpay payloads for developer testing and demonstration."""
    return FIXTURES


@router.get(
    "/tunnel-guide",
    response_model=WebhookTunnelGuide,
    summary="Get local webhook tunnel forwarding instructions",
)
def get_webhook_tunnel_guide() -> WebhookTunnelGuide:
    """Returns instructions and commands for forwarding live Razorpay webhooks to local RecoverAI."""
    app_settings = get_settings()
    configured = bool(
        app_settings.RAZORPAY_KEY_ID
        and app_settings.RAZORPAY_KEY_SECRET
        and app_settings.RAZORPAY_WEBHOOK_SECRET
    )

    return WebhookTunnelGuide(
        service_name="RecoverAI Webhook Gateway Forwarder",
        target_url="http://localhost:8000/api/v1/webhooks/razorpay",
        security_notice="Local tunnels forward live Razorpay test webhooks securely. Every forwarded event undergoes strict HMAC-SHA256 signature verification and idempotency deduplication. NEVER use production Razorpay credentials.",
        razorpay_configured=configured,
        test_mode_only=True,
        tunnel_options=[
            {
                "tool": "ngrok",
                "command": "ngrok http 8000",
                "webhook_url": "https://<your-ngrok-subdomain>.ngrok-free.app/api/v1/webhooks/razorpay",
                "notes": "Add this URL in Razorpay Dashboard > Settings > Webhooks with your configured RAZORPAY_WEBHOOK_SECRET.",
            },
            {
                "tool": "Cloudflare Tunnel (cloudflared)",
                "command": "cloudflared tunnel --url http://localhost:8000",
                "webhook_url": "https://<your-cf-subdomain>.trycloudflare.com/api/v1/webhooks/razorpay",
                "notes": "Free quick tunnel without requiring account signup.",
            },
        ],
    )


@router.post(
    "/test/razorpay",
    response_model=WebhookTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute test synthetic Razorpay webhook event",
)
def execute_test_webhook(
    payload: WebhookTestRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WebhookTestResponse:
    """
    Developer Console test endpoint:
    Executes a synthetic Razorpay webhook event through the complete cryptographic signature,
    event deduplication, revenue at risk calculation, and audit trail pipeline without live money.
    """
    event_dict = payload.payload.copy()
    if "event" not in event_dict:
        event_dict["event"] = payload.event_type

    # Ensure event ID exists for idempotency
    event_id = event_dict.get("id") or f"evt_demo_{abs(hash(json.dumps(event_dict, sort_keys=True))) % 10000000:07d}"
    event_dict["id"] = event_id

    raw_body = json.dumps(event_dict, separators=(",", ":")).encode("utf-8")
    app_settings = get_settings()
    secret = app_settings.RAZORPAY_WEBHOOK_SECRET or "rzp_test_mock_webhook_secret_default"
    signature = create_hmac_sha256_signature(raw_body=raw_body, secret=secret)


    request_id = getattr(request.state, "request_id", "test-console-req")

    result = WebhookService.process_razorpay_webhook(
        db=db,
        raw_body=raw_body,
        signature=signature,
        webhook_secret=secret,
        event_id_header=event_id,
        actor="developer_webhook_console",
    )

    # Inspect resulting database entities
    payment_rzp_id = (
        event_dict.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
    )
    payment_id = None
    revenue_record_id = None
    recovery_case_id = None

    if payment_rzp_id:
        payment = db.scalar(select(Payment).where(Payment.razorpay_payment_id == payment_rzp_id))
        if payment:
            payment_id = payment.id
            revenue = db.scalar(select(RevenueRecord).where(RevenueRecord.payment_id == payment.id))
            if revenue:
                revenue_record_id = revenue.id
                case = db.scalar(select(RecoveryCase).where(RecoveryCase.revenue_record_id == revenue.id))
                if case:
                    recovery_case_id = case.id

    is_dup = result.get("status") == "duplicate"
    audit_action = "razorpay_webhook_duplicate" if is_dup else "razorpay_webhook_processed"

    return WebhookTestResponse(
        status=result["status"],
        event_id=result["event_id"],
        event_type=result.get("event_type", payload.event_type),
        message=result["message"],
        is_duplicate=is_dup,
        payment_id=payment_id,
        revenue_record_id=revenue_record_id,
        recovery_case_id=result.get("recovery_case_id") or recovery_case_id,
        orchestration_status=result.get("orchestration_status"),
        orchestration_message=result.get("orchestration_message"),
        approval_id=result.get("approval_id"),
        request_id=request_id,
        audit_action=audit_action,
    )


@router.get(
    "/recent-events",
    response_model=WebhookRecentEventsResponse,
    summary="Get recent webhook events for live monitor",
)
def get_recent_webhook_events(
    limit: int = Query(25, ge=1, le=100, description="Max events to return"),
    db: Session = Depends(get_db),
) -> WebhookRecentEventsResponse:
    """
    Returns recent webhook audit entries for the live monitoring dashboard.
    Filters for razorpay_webhook_* actions and resolves associated case/payment IDs
    from event_metadata.
    """
    query = (
        select(AuditLog)
        .where(
            AuditLog.action.in_(["razorpay_webhook_processed", "razorpay_webhook_duplicate"])
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    rows = list(db.scalars(query).all())
    total = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action.in_(["razorpay_webhook_processed", "razorpay_webhook_duplicate"]))
    ) or 0

    items: list[WebhookRecentEvent] = []
    for row in rows:
        meta = row.event_metadata or {}
        items.append(
            WebhookRecentEvent(
                id=row.id,
                event_type=meta.get("event_type", row.action),
                event_id=meta.get("event_id"),
                status="duplicate" if row.action == "razorpay_webhook_duplicate" else "processed",
                recovery_case_id=meta.get("recovery_case_id"),
                payment_id=meta.get("payment_id"),
                orchestration_status=meta.get("orchestration_status"),
                message=meta.get("message"),
                timestamp=row.timestamp,
                is_duplicate=row.action == "razorpay_webhook_duplicate",
            )
        )
    return WebhookRecentEventsResponse(items=items, total=total)
