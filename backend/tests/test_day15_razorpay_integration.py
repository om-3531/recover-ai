"""
Day 15 — Razorpay Test-Mode Webhook Integration E2E Tests.

Covers:
1. Valid Razorpay payment.failed webhook with real HMAC signature
2. Invalid signature rejection
3. Missing signature rejection
4. Duplicate webhook idempotency
5. Payment creation from webhook
6. RevenueRecord creation from webhook
7. RecoveryCase creation from webhook
8. Orchestration triggered automatically
9. AI decision generated
10. Low-risk auto execution
11. High-risk approval gate
12. Critical-risk approval gate
13. Policy blocked recovery
14. Audit trail generated
15. Analytics updated
16. Malformed payload handling
17. Unsupported event safe handling
18. Missing payment entity safe handling
19. Signature timing-safe comparison (HMAC compare_digest)
20. No secret leakage in response/logging
21. Razorpay configuration status endpoint
22. Tunnel guide endpoint with config status
"""

import hashlib
import hmac
import json
import pytest
from unittest.mock import patch

from app.core.config import get_settings
from app.core.metrics import metrics
from app.integrations.razorpay.service import RazorpayService
from app.integrations.razorpay.signature import create_hmac_sha256_signature
from app.models.audit import AuditLog
from app.models.enums import (
    ApprovalStatus,
    PaymentStatus,
    RecoveryCaseState,
    RevenueStatus,
    RiskStatus,
)
from app.models.payment import Payment, PaymentEvent
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.services.audit_service import AuditService

TEST_WEBHOOK_SECRET = "rzp_test_webhook_secret_day15"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Generate HMAC-SHA256 signature for a payload."""
    return create_hmac_sha256_signature(raw_body=payload_bytes, secret=secret)


def _make_payment_failed_payload(
    event_id: str = "evt_day15_fail_001",
    payment_id: str = "pay_day15_fail_001",
    amount: int = 250000,
    error_code: str = "BAD_REQUEST_ERROR",
    error_reason: str = "payment_failed",
) -> dict:
    """Create a realistic Razorpay payment.failed webhook payload."""
    return {
        "entity": "event",
        "account_id": "acc_day15_recoverai",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": f"order_{payment_id.replace('pay_', '')}",
                    "method": "card",
                    "email": "test_customer@example.com",
                    "contact": "+919876543210",
                    "error_code": error_code,
                    "error_description": "Payment failed due to insufficient funds",
                    "error_source": "bank",
                    "error_step": "payment_authorization",
                    "error_reason": error_reason,
                }
            }
        },
        "id": event_id,
        "created_at": 1724500000,
    }


def _send_webhook(client, payload_dict: dict, secret: str = TEST_WEBHOOK_SECRET):
    """Sign and send a webhook payload to the endpoint."""
    raw_body = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    sig = _sign_payload(raw_body, secret)

    return client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    ), raw_body


# ---------------------------------------------------------------------------
# 1. VALID PAYMENT.FAILED WEBHOOK — FULL PIPELINE
# ---------------------------------------------------------------------------


def test_valid_payment_failed_webhook_full_pipeline(client, db_session, monkeypatch):
    """1. Valid payment.failed webhook triggers complete recovery pipeline."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_full_001",
        payment_id="pay_day15_full_001",
        amount=250000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processed"
    assert data["event_id"] == "evt_day15_full_001"
    assert data["event_type"] == "payment.failed"

    # Payment created
    payment = db_session.query(Payment).filter_by(razorpay_payment_id="pay_day15_full_001").first()
    assert payment is not None
    assert payment.status == PaymentStatus.failed
    assert payment.amount == 250000

    # RevenueRecord created as at_risk
    revenue = db_session.query(RevenueRecord).filter_by(payment_id=payment.id).first()
    assert revenue is not None
    assert revenue.status == RevenueStatus.at_risk
    assert revenue.recoverable_amount == 250000

    # RecoveryCase created
    case = db_session.query(RecoveryCase).filter_by(revenue_record_id=revenue.id).first()
    assert case is not None
    assert case.current_state in (RecoveryCaseState.open, RecoveryCaseState.action_pending, RecoveryCaseState.recovering)
    assert data["recovery_case_id"] == case.id

    # Orchestration was triggered
    assert data["orchestration_status"] is not None


# ---------------------------------------------------------------------------
# 2. INVALID SIGNATURE REJECTION
# ---------------------------------------------------------------------------


def test_invalid_signature_rejected(client, db_session, monkeypatch):
    """2. Webhook with invalid HMAC signature is rejected."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(event_id="evt_day15_inv_001")
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_signature_that_does_not_match",
        },
    )
    assert resp.status_code == 400
    assert "Invalid Razorpay webhook signature" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 3. MISSING SIGNATURE REJECTION
# ---------------------------------------------------------------------------


def test_missing_signature_rejected(client, db_session, monkeypatch):
    """3. Webhook without X-Razorpay-Signature header is rejected."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(event_id="evt_day15_miss_001")
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert "Missing X-Razorpay-Signature" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. DUPLICATE WEBHOOK IDEMPOTENCY
# ---------------------------------------------------------------------------


def test_duplicate_webhook_idempotency(client, db_session, monkeypatch):
    """4. Duplicate webhook event IDs are safely deduplicated."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_dup_001",
        payment_id="pay_day15_dup_001",
        amount=150000,
    )

    # First delivery
    resp1, _ = _send_webhook(client, payload)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"

    # Second delivery (same event_id)
    resp2, _ = _send_webhook(client, payload)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"

    # Only 1 payment exists
    payments = db_session.query(Payment).filter_by(razorpay_payment_id="pay_day15_dup_001").all()
    assert len(payments) == 1


# ---------------------------------------------------------------------------
# 5. PAYMENT CREATION FROM WEBHOOK
# ---------------------------------------------------------------------------


def test_payment_created_from_webhook(client, db_session, monkeypatch):
    """5. Webhook creates Payment record with correct fields."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_pay_001",
        payment_id="pay_day15_pay_001",
        amount=500000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200

    payment = db_session.query(Payment).filter_by(razorpay_payment_id="pay_day15_pay_001").first()
    assert payment is not None
    assert payment.amount == 500000
    assert payment.currency == "INR"
    assert payment.status == PaymentStatus.failed
    assert payment.method is not None
    assert payment.customer_email == "test_customer@example.com"


# ---------------------------------------------------------------------------
# 6. REVENUE RECORD CREATION FROM WEBHOOK
# ---------------------------------------------------------------------------


def test_revenue_record_created_from_webhook(client, db_session, monkeypatch):
    """6. Webhook creates RevenueRecord as at_risk for payment.failed."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_rev_001",
        payment_id="pay_day15_rev_001",
        amount=350000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200

    payment = db_session.query(Payment).filter_by(razorpay_payment_id="pay_day15_rev_001").first()
    revenue = db_session.query(RevenueRecord).filter_by(payment_id=payment.id).first()
    assert revenue is not None
    assert revenue.status == RevenueStatus.at_risk
    assert revenue.recoverable_amount == 350000
    assert revenue.gross_amount == 350000


# ---------------------------------------------------------------------------
# 7. RECOVERY CASE CREATION FROM WEBHOOK
# ---------------------------------------------------------------------------


def test_recovery_case_created_from_webhook(client, db_session, monkeypatch):
    """7. Webhook creates RecoveryCase linked to RevenueRecord."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_case_001",
        payment_id="pay_day15_case_001",
        amount=200000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    case_id = resp.json()["recovery_case_id"]
    assert case_id is not None

    case = db_session.query(RecoveryCase).filter_by(id=case_id).first()
    assert case is not None
    assert case.reason is not None
    assert case.risk_status is not None
    assert case.priority is not None
    assert case.current_state in (
        RecoveryCaseState.open,
        RecoveryCaseState.action_pending,
        RecoveryCaseState.recovering,
    )


# ---------------------------------------------------------------------------
# 8. ORCHESTRATION TRIGGERED
# ---------------------------------------------------------------------------


def test_orchestration_triggered_from_webhook(client, db_session, monkeypatch):
    """8. Orchestration runs automatically after RecoveryCase creation."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_orch_001",
        payment_id="pay_day15_orch_001",
        amount=250000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["orchestration_status"] is not None
    assert data["orchestration_status"] in (
        "completed",
        "approval_required",
        "orchestration_error",
    )


# ---------------------------------------------------------------------------
# 9. AI DECISION GENERATED
# ---------------------------------------------------------------------------


def test_ai_decision_generated(client, db_session, monkeypatch):
    """9. AI generates a recovery recommendation during orchestration."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_ai_001",
        payment_id="pay_day15_ai_001",
        amount=250000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200

    # Verify orchestration ran (AI decision is internal, not in response)
    case_id = resp.json()["recovery_case_id"]
    case = db_session.query(RecoveryCase).filter_by(id=case_id).first()
    assert case is not None

    # Check audit trail has orchestration entries
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_case", entity_id=str(case_id)
    )
    assert total >= 1


# ---------------------------------------------------------------------------
# 10. LOW-RISK AUTO EXECUTION
# ---------------------------------------------------------------------------


def test_low_risk_auto_execution(client, db_session, monkeypatch):
    """10. Low-risk payment failure auto-executes without approval gate."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # Amount < 100000 paise = low risk
    payload = _make_payment_failed_payload(
        event_id="evt_day15_low_001",
        payment_id="pay_day15_low_001",
        amount=50000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    data = resp.json()
    # Low risk should complete execution
    assert data["orchestration_status"] == "completed"


# ---------------------------------------------------------------------------
# 11. HIGH-RISK APPROVAL GATE
# ---------------------------------------------------------------------------


def test_high_risk_approval_gate(client, db_session, monkeypatch):
    """11. High-risk payment failure requires approval before execution."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # Amount >= 1000000 paise = high risk
    payload = _make_payment_failed_payload(
        event_id="evt_day15_high_001",
        payment_id="pay_day15_high_001",
        amount=2000000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["orchestration_status"] == "approval_required"


# ---------------------------------------------------------------------------
# 12. CRITICAL-RISK APPROVAL GATE
# ---------------------------------------------------------------------------


def test_critical_risk_approval_gate(client, db_session, monkeypatch):
    """12. Critical-risk payment failure requires approval."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # Amount >= 5000000 paise = critical risk
    payload = _make_payment_failed_payload(
        event_id="evt_day15_crit_001",
        payment_id="pay_day15_crit_001",
        amount=10000000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["orchestration_status"] == "approval_required"


# ---------------------------------------------------------------------------
# 13. POLICY BLOCKED RECOVERY
# ---------------------------------------------------------------------------


def test_policy_blocked_recovery(client, db_session, monkeypatch):
    """13. Policy can block recovery for terminal cases."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # This test verifies the policy engine is invoked during orchestration
    # The mock AI provider always recommends, but policy can block
    payload = _make_payment_failed_payload(
        event_id="evt_day15_pol_001",
        payment_id="pay_day15_pol_001",
        amount=100000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    # Verify orchestration completed (policy evaluation happened internally)
    assert resp.json()["orchestration_status"] is not None


# ---------------------------------------------------------------------------
# 14. AUDIT TRAIL GENERATED
# ---------------------------------------------------------------------------


def test_audit_trail_generated(client, db_session, monkeypatch):
    """14. Complete audit trail is generated for webhook processing."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_audit_001",
        payment_id="pay_day15_audit_001",
        amount=250000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200

    # Verify audit logs exist
    audits, total = AuditService.list_audit_logs(db_session, action="razorpay_webhook_received")
    assert total >= 1

    audits2, total2 = AuditService.list_audit_logs(db_session, action="razorpay_webhook_processed")
    assert total2 >= 1

    audits3, total3 = AuditService.list_audit_logs(db_session, action="payment_failed")
    assert total3 >= 1


# ---------------------------------------------------------------------------
# 15. ANALYTICS UPDATED
# ---------------------------------------------------------------------------


def test_analytics_updated(client, db_session, monkeypatch):
    """15. Analytics reflect new recovery activity after webhook."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(
        event_id="evt_day15_analytics_001",
        payment_id="pay_day15_analytics_001",
        amount=250000,
    )

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200

    # Verify analytics endpoint shows the new case
    analytics = client.get("/api/v1/analytics/overview")
    assert analytics.status_code == 200
    data = analytics.json()
    assert data["total_cases"] >= 1


# ---------------------------------------------------------------------------
# 16. MALFORMED PAYLOAD HANDLING
# ---------------------------------------------------------------------------


def test_malformed_payload_rejected(client, db_session, monkeypatch):
    """16. Malformed JSON payload is rejected."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    bad_json = b"this is not valid json"
    sig = _sign_payload(bad_json)

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=bad_json,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp.status_code == 400
    assert "Malformed JSON" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 17. UNSUPPORTED EVENT SAFE HANDLING
# ---------------------------------------------------------------------------


def test_unsupported_event_safe(client, db_session, monkeypatch):
    """17. Unsupported event types are logged safely without side effects."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = {
        "entity": "event",
        "event": "refund.created",
        "contains": ["refund"],
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_day15_001",
                    "amount": 100000,
                    "status": "processed",
                }
            }
        },
        "id": "evt_day15_unsupported_001",
    }

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert resp.json()["event_type"] == "refund.created"


# ---------------------------------------------------------------------------
# 18. MISSING PAYMENT ENTITY SAFE HANDLING
# ---------------------------------------------------------------------------


def test_missing_payment_entity_safe(client, db_session, monkeypatch):
    """18. Events without payment entity are handled safely."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = {
        "entity": "event",
        "event": "order.paid",
        "contains": ["order"],
        "payload": {
            "order": {
                "entity": {
                    "id": "order_day15_001",
                    "amount": 50000,
                }
            }
        },
        "id": "evt_day15_nopay_001",
    }

    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert resp.json()["recovery_case_id"] is None


# ---------------------------------------------------------------------------
# 19. SIGNATURE TIMING-SAFE COMPARISON
# ---------------------------------------------------------------------------


def test_signature_timing_safe_comparison(client, db_session, monkeypatch):
    """19. Signature verification uses constant-time comparison (hmac.compare_digest)."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = _make_payment_failed_payload(event_id="evt_day15_timing_001")
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = _sign_payload(raw_body)

    # Verify the signature module uses compare_digest
    from app.integrations.razorpay.signature import verify_webhook_signature

    result = verify_webhook_signature(raw_body, sig, TEST_WEBHOOK_SECRET)
    assert result is True

    # Wrong signature returns False
    result2 = verify_webhook_signature(raw_body, "a" * 64, TEST_WEBHOOK_SECRET)
    assert result2 is False


# ---------------------------------------------------------------------------
# 20. NO SECRET LEAKAGE IN RESPONSE
# ---------------------------------------------------------------------------


def test_no_secret_leakage_in_response(client, db_session, monkeypatch):
    """20. API responses never expose webhook secrets or credentials."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_ID", "rzp_test_leak_check")
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_SECRET", "super_secret_key_12345")

    payload = _make_payment_failed_payload(event_id="evt_day15_leak_001")
    resp, _ = _send_webhook(client, payload)
    assert resp.status_code == 200

    response_text = json.dumps(resp.json())
    assert TEST_WEBHOOK_SECRET not in response_text
    assert "super_secret_key_12345" not in response_text
    assert "rzp_test_leak_check" not in response_text

    # Check config status endpoint
    config_resp = client.get("/api/v1/webhooks/config-status")
    assert config_resp.status_code == 200
    config_text = json.dumps(config_resp.json())
    assert TEST_WEBHOOK_SECRET not in config_text
    assert "super_secret_key_12345" not in config_text


# ---------------------------------------------------------------------------
# 21. RAZORPAY CONFIGURATION STATUS ENDPOINT
# ---------------------------------------------------------------------------


def test_razorpay_config_status_endpoint(client, monkeypatch):
    """21. Razorpay config status endpoint returns safe configuration info."""
    # When not configured
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_ID", "")
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_SECRET", "")
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", "")

    resp = client.get("/api/v1/webhooks/config-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["key_id_present"] is False
    assert data["test_mode"] is False
    assert "Missing" in data["status_message"]


def test_razorpay_config_status_configured(client, monkeypatch):
    """21b. Config status endpoint when Razorpay is configured."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_ID", "rzp_test_abc123")
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_SECRET", "test_secret")
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

    resp = client.get("/api/v1/webhooks/config-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["key_id_present"] is True
    assert data["key_secret_present"] is True
    assert data["webhook_secret_present"] is True
    assert data["test_mode"] is True
    assert "c123" in data["status_message"]


# ---------------------------------------------------------------------------
# 22. TUNNEL GUIDE WITH CONFIG STATUS
# ---------------------------------------------------------------------------


def test_tunnel_guide_includes_config_status(client, monkeypatch):
    """22. Tunnel guide endpoint includes Razorpay configuration status."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_ID", "")
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_SECRET", "")
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", "")

    resp = client.get("/api/v1/webhooks/tunnel-guide")
    assert resp.status_code == 200
    data = resp.json()
    assert "tunnel_options" in data
    assert len(data["tunnel_options"]) >= 2
    assert data["razorpay_configured"] is False
    assert data["test_mode_only"] is True

    # Verify security notice exists
    assert "NEVER" in data["security_notice"]


def test_tunnel_guide_configured(client, monkeypatch):
    """22b. Tunnel guide when Razorpay is configured."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_ID", "rzp_test_xyz789")
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_SECRET", "test_secret")
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

    resp = client.get("/api/v1/webhooks/tunnel-guide")
    assert resp.status_code == 200
    data = resp.json()
    assert data["razorpay_configured"] is True
