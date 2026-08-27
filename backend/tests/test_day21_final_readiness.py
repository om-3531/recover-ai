"""
Tests for Day 21 — Final Buildathon Readiness Pass.

Covers:
- Configuration correctness and safe defaults
- Demo mode safety gate
- Security: no secret leakage in API responses
- Complete approval workflow lifecycle
- Pipeline: low-risk auto-execution
- Pipeline: high-risk approval gate
- Idempotency of duplicate webhook events
- Analytics consistency after seeding
- Health endpoint returns expected fields
- Approval list pagination
- Audit trail completeness for decisions
- Mock provider defaults
"""

import pytest

from app.core.config import get_settings


# ---------------------------------------------------------------------------
# 1. CONFIGURATION CORRECTNESS
# ---------------------------------------------------------------------------


def test_ai_provider_defaults_to_mock():
    """AI_PROVIDER must default to mock for safe demo operation."""
    settings = get_settings()
    assert settings.AI_PROVIDER == "mock"


def test_demo_mode_defaults_to_true():
    """DEMO_MODE must default to True for safe demo operation."""
    settings = get_settings()
    assert settings.DEMO_MODE is True


def test_razorpay_keys_default_empty():
    """Razorpay credentials must default to empty strings (no real keys)."""
    settings = get_settings()
    assert settings.RAZORPAY_KEY_ID == ""
    assert settings.RAZORPAY_KEY_SECRET == ""
    assert settings.RAZORPAY_WEBHOOK_SECRET == ""


def test_communication_providers_default_empty():
    """All communication provider keys must default to empty strings."""
    settings = get_settings()
    assert settings.SENDGRID_API_KEY == ""
    assert settings.TWILIO_ACCOUNT_SID == ""
    assert settings.TWILIO_AUTH_TOKEN == ""
    assert settings.WHATSAPP_ACCESS_TOKEN == ""


def test_frontend_origin_is_localhost():
    """CORS origin must default to localhost (not a production domain)."""
    settings = get_settings()
    assert "localhost" in settings.FRONTEND_ORIGIN or "127.0.0.1" in settings.FRONTEND_ORIGIN


def test_webhook_allow_insecure_http_false():
    """WEBHOOK_ALLOW_INSECURE_HTTP must default to False."""
    settings = get_settings()
    assert settings.WEBHOOK_ALLOW_INSECURE_HTTP is False


# ---------------------------------------------------------------------------
# 2. DEMO MODE SAFETY GATE
# ---------------------------------------------------------------------------


def test_demo_seed_blocked_when_demo_mode_false(client, monkeypatch):
    """Demo seed endpoint returns 403 when DEMO_MODE is disabled."""
    monkeypatch.setattr("app.demo.service.settings", type("S", (), {"DEMO_MODE": False})())
    resp = client.post("/api/v1/demo/seed", json={"scenario": "all", "count": 5})
    assert resp.status_code == 403


def test_demo_reset_blocked_when_demo_mode_false(client, monkeypatch):
    """Demo reset endpoint returns 403 when DEMO_MODE is disabled."""
    monkeypatch.setattr("app.demo.service.settings", type("S", (), {"DEMO_MODE": False})())
    resp = client.post("/api/v1/demo/reset")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. SECURITY: NO SECRET LEAKAGE
# ---------------------------------------------------------------------------


def test_config_status_does_not_expose_secrets(client):
    """Config status endpoint must never expose actual secret values."""
    resp = client.get("/api/v1/webhooks/config-status")
    assert resp.status_code == 200
    body = resp.json()
    # Should contain boolean flags, not actual secrets
    assert "key_id_present" in body
    assert "key_secret_present" in body
    assert "configured" in body
    # Ensure no raw secret values appear in the response text
    text = resp.text
    assert "rzp_" not in text.lower()


def test_health_endpoint_returns_expected_fields(client):
    """Health endpoint must return status and service name."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "service" in body


# ---------------------------------------------------------------------------
# 4. COMPLETE APPROVAL WORKFLOW LIFECYCLE
# ---------------------------------------------------------------------------


def test_full_approval_lifecycle_via_api(client, db_session):
    """Verify the complete approve→execute lifecycle via REST API."""
    from app.models.payment import Payment
    from app.models.revenue import RevenueRecord
    from app.models.recovery import RecoveryCase
    from app.models.enums import (
        PaymentStatus, PaymentMethod, RevenueStatus,
        RiskStatus, RecoveryPriority, RecoveryCaseState,
    )
    from app.approval.service import ApprovalService
    from app.approval.schemas import ApprovalCreateRequest
    from app.models.enums import RecoveryActionType, RecoveryActionChannel

    # Create test data
    payment = Payment(
        razorpay_payment_id="pay_day21_lc_001", amount=500000,
        currency="INR", status=PaymentStatus.failed, method=PaymentMethod.card,
    )
    db_session.add(payment)
    db_session.flush()
    revenue = RevenueRecord(
        payment_id=payment.id, gross_amount=500000, recoverable_amount=500000,
        currency="INR", status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()
    case = RecoveryCase(
        revenue_record_id=revenue.id, reason="test_lifecycle",
        risk_status=RiskStatus.high, priority=RecoveryPriority.high,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # Create approval
    req = ApprovalCreateRequest(
        recovery_case_id=case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    approval = ApprovalService.create_approval(db_session, req)

    # Verify via API: list shows it as pending
    resp = client.get("/api/v1/approvals", params={"status": "pending"})
    assert resp.status_code == 200
    assert any(a["id"] == approval.id for a in resp.json()["items"])

    # Approve via API
    resp = client.post(f"/api/v1/approvals/{approval.id}/approve", json={"approved_by": "readiness_test"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Execute via API
    resp = client.post(f"/api/v1/approvals/{approval.id}/execute")
    assert resp.status_code == 200
    assert resp.json()["result"]["success"] is True

    # Verify case state updated
    db_session.refresh(case)
    assert case.current_state == RecoveryCaseState.recovering


# ---------------------------------------------------------------------------
# 5. PIPELINE: LOW-RISK AUTO-EXECUTION
# ---------------------------------------------------------------------------


def test_low_risk_webhook_auto_completes(client, db_session):
    """Low-risk payment failure webhook should auto-complete without approval gate."""
    resp = client.post(
        "/api/v1/webhooks/test/razorpay",
        json={
            "event_type": "payment.failed",
            "payload": {
                "event": "payment.failed",
                "id": "evt_day21_lowrisk",
                "payload": {"payment": {"entity": {
                    "id": "pay_day21_low", "amount": 25000,
                    "currency": "INR", "status": "failed", "method": "upi",
                    "created_at": 1724000000, "order_id": "order_day21_low",
                }}},
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processed"
    assert data["orchestration_status"] == "completed"


# ---------------------------------------------------------------------------
# 6. PIPELINE: HIGH-RISK APPROVAL GATE
# ---------------------------------------------------------------------------


def test_high_risk_webhook_requires_approval(client, db_session):
    """High-risk payment failure webhook should trigger approval gate."""
    resp = client.post(
        "/api/v1/webhooks/test/razorpay",
        json={
            "event_type": "payment.failed",
            "payload": {
                "event": "payment.failed",
                "id": "evt_day21_highrisk",
                "payload": {"payment": {"entity": {
                    "id": "pay_day21_high", "amount": 1500000,
                    "currency": "INR", "status": "failed", "method": "card",
                    "created_at": 1724000000, "order_id": "order_day21_high",
                }}},
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processed"
    assert data["orchestration_status"] == "approval_required"
    assert data["approval_id"] is not None


# ---------------------------------------------------------------------------
# 7. IDEMPOTENCY OF DUPLICATE WEBHOOK EVENTS
# ---------------------------------------------------------------------------


def test_duplicate_webhook_event_is_detected(client, db_session):
    """Sending the same event ID twice should detect the duplicate."""
    payload = {
        "event_type": "payment.failed",
        "payload": {
            "event": "payment.failed",
            "id": "evt_day21_dup_test",
            "payload": {"payment": {"entity": {
                "id": "pay_day21_dup", "amount": 50000,
                "currency": "INR", "status": "failed", "method": "upi",
                "created_at": 1724000000, "order_id": "order_day21_dup",
            }}},
        },
    }
    resp1 = client.post("/api/v1/webhooks/test/razorpay", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["is_duplicate"] is False

    resp2 = client.post("/api/v1/webhooks/test/razorpay", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["is_duplicate"] is True


# ---------------------------------------------------------------------------
# 8. ANALYTICS CONSISTENCY AFTER SEEDING
# ---------------------------------------------------------------------------


def test_overview_analytics_returns_valid_data(client, db_session):
    """Overview analytics must return numeric fields without errors."""
    resp = client.get("/api/v1/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_recoverable_amount" in body
    assert "total_recovered_amount" in body
    assert "recovery_rate" in body
    assert isinstance(body["total_recoverable_amount"], (int, float))
    assert isinstance(body["recovery_rate"], (int, float))


# ---------------------------------------------------------------------------
# 9. APPROVAL LIST PAGINATION
# ---------------------------------------------------------------------------


def test_approval_list_respects_limit(client, db_session):
    """Approval list must respect the limit parameter."""
    from app.models.payment import Payment
    from app.models.revenue import RevenueRecord
    from app.models.recovery import RecoveryCase
    from app.models.enums import (
        PaymentStatus, PaymentMethod, RevenueStatus,
        RiskStatus, RecoveryPriority, RecoveryCaseState,
        RecoveryActionType, RecoveryActionChannel,
    )
    from app.approval.service import ApprovalService
    from app.approval.schemas import ApprovalCreateRequest

    payment = Payment(
        razorpay_payment_id="pay_day21_page", amount=100000,
        currency="INR", status=PaymentStatus.failed, method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()
    revenue = RevenueRecord(
        payment_id=payment.id, gross_amount=100000, recoverable_amount=100000,
        currency="INR", status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()
    case = RecoveryCase(
        revenue_record_id=revenue.id, reason="test_pagination",
        risk_status=RiskStatus.low, priority=RecoveryPriority.low,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # Create 3 approvals
    for i in range(3):
        req = ApprovalCreateRequest(
            recovery_case_id=case.id,
            action_type=RecoveryActionType.email_reminder,
            channel=RecoveryActionChannel.email,
        )
        ApprovalService.create_approval(db_session, req)

    resp = client.get("/api/v1/approvals", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2
    assert resp.json()["total"] >= 3


# ---------------------------------------------------------------------------
# 10. AUDIT TRAIL COMPLETENESS
# ---------------------------------------------------------------------------


def test_approval_decision_creates_audit_entry(client, db_session):
    """Approving an approval must create an audit log entry."""
    from app.models.payment import Payment
    from app.models.revenue import RevenueRecord
    from app.models.recovery import RecoveryCase
    from app.models.enums import (
        PaymentStatus, PaymentMethod, RevenueStatus,
        RiskStatus, RecoveryPriority, RecoveryCaseState,
        RecoveryActionType, RecoveryActionChannel,
    )
    from app.approval.service import ApprovalService
    from app.approval.schemas import ApprovalCreateRequest
    from app.services.audit_service import AuditService

    payment = Payment(
        razorpay_payment_id="pay_day21_audit", amount=100000,
        currency="INR", status=PaymentStatus.failed, method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()
    revenue = RevenueRecord(
        payment_id=payment.id, gross_amount=100000, recoverable_amount=100000,
        currency="INR", status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()
    case = RecoveryCase(
        revenue_record_id=revenue.id, reason="test_audit",
        risk_status=RiskStatus.low, priority=RecoveryPriority.low,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    req = ApprovalCreateRequest(
        recovery_case_id=case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    approval = ApprovalService.create_approval(db_session, req)

    # Approve via API
    resp = client.post(
        f"/api/v1/approvals/{approval.id}/approve",
        json={"approved_by": "audit_readiness_test"},
    )
    assert resp.status_code == 200

    # Verify audit trail
    audits, total = AuditService.list_audit_logs(
        db_session,
        entity_type="recovery_approval",
        entity_id=str(approval.id),
    )
    assert any(a.action == "approval_approved" for a in audits)
    assert any(a.actor == "audit_readiness_test" for a in audits)


# ---------------------------------------------------------------------------
# 11. MOCK PROVIDER DEFAULTS
# ---------------------------------------------------------------------------


def test_system_status_includes_demo_mode(client):
    """System status endpoint must return demo_mode field."""
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "demo_mode" in body
    assert body["demo_mode"] is True


def test_system_providers_returns_ai_provider(client):
    """System providers endpoint must include ai_engine channel."""
    resp = client.get("/api/v1/system/providers")
    assert resp.status_code == 200
    body = resp.json()
    assert "providers" in body
    channels = [p["channel"] for p in body["providers"]]
    assert "ai_engine" in channels
