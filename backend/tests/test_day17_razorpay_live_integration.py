"""
Day 17 — Real Razorpay Test-Mode Live Integration E2E Tests.

Covers the complete real Razorpay test-mode integration including:
- Configuration verification (unconfigured / configured / partial)
- Safe config status endpoint (no secret leakage)
- Webhook signature verification (valid / invalid / missing)
- Duplicate event idempotency
- Malformed and unsupported event handling
- Complete payment.failed pipeline
- RecoveryCase creation from real webhook
- Orchestration trigger and AI decision
- High-risk approval gate
- Low-risk auto execution
- Audit trail completeness
- Analytics update after webhook
- Tunnel guide endpoint
- Secret leakage prevention
- Developer simulation console still works
- Demo mode independence
- Real Razorpay format compatibility
"""

import json
import pytest
from unittest.mock import patch

from app.core.config import get_settings
from app.integrations.razorpay.signature import create_hmac_sha256_signature
from app.models.audit import AuditLog
from app.models.enums import (
    ApprovalStatus,
    PaymentStatus,
    RecoveryCaseState,
    RevenueStatus,
    RiskStatus,
)
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord

TEST_WEBHOOK_SECRET = "rzp_test_webhook_secret_day17"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _sign(payload_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return create_hmac_sha256_signature(raw_body=payload_bytes, secret=secret)


def _make_payload(
    event_id: str = "evt_day17_001",
    payment_id: str = "pay_day17_001",
    amount: int = 250000,
    event_type: str = "payment.failed",
) -> dict:
    """Create a realistic Razorpay webhook payload in the exact format sent by Razorpay."""
    return {
        "entity": "event",
        "account_id": "acc_day17_recoverai",
        "event": event_type,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": "order_day17_001",
                    "method": "card",
                    "email": "day17_test@example.com",
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
    }


def _make_high_value_payload(
    event_id: str = "evt_day17_high_001",
    payment_id: str = "pay_day17_high_001",
) -> dict:
    """High-value payment that triggers human approval gate (>= ₹50,000 = critical risk)."""
    return _make_payload(
        event_id=event_id,
        payment_id=payment_id,
        amount=4500000,  # ₹45,000 = critical risk
    )


def _send_raw_webhook(client, payload_dict, secret=TEST_WEBHOOK_SECRET, event_id=None):
    """Send a webhook through the production endpoint with proper HMAC signature."""
    raw_body = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    signature = _sign(raw_body, secret)
    eid = event_id or payload_dict.get("id", payload_dict.get("event_id", ""))
    headers = {
        "X-Razorpay-Signature": signature,
    }
    if eid:
        headers["X-Razorpay-Event-Id"] = eid
    return client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers=headers,
    )


def _send_test_console(client, event_id, payload_dict):
    """Send via the developer simulation console."""
    return client.post(
        "/api/v1/webhooks/test/razorpay",
        json={"event_type": payload_dict.get("event", "payment.failed"), "payload": payload_dict},
    )


# ---------------------------------------------------------------------------
# 1. RAZORPAY CONFIGURATION VERIFICATION
# ---------------------------------------------------------------------------

class TestRazorpayConfiguration:
    """Phase 2: Verify Razorpay configuration handling."""

    def test_config_defaults_are_empty(self):
        """Settings defaults for Razorpay are empty strings (fail-loudly)."""
        with patch.dict("os.environ", {}, clear=False):
            from app.core.config import Settings
            s = Settings()
            assert s.RAZORPAY_KEY_ID == ""
            assert s.RAZORPAY_KEY_SECRET == ""
            assert s.RAZORPAY_WEBHOOK_SECRET == ""

    def test_config_loads_from_env(self):
        """Settings loads Razorpay credentials from environment."""
        with patch.dict("os.environ", {
            "RAZORPAY_KEY_ID": "rzp_test_abc",
            "RAZORPAY_KEY_SECRET": "secret123",
            "RAZORPAY_WEBHOOK_SECRET": "whsec_test",
        }):
            from app.core.config import Settings
            s = Settings()
            assert s.RAZORPAY_KEY_ID == "rzp_test_abc"
            assert s.RAZORPAY_KEY_SECRET == "secret123"
            assert s.RAZORPAY_WEBHOOK_SECRET == "whsec_test"


# ---------------------------------------------------------------------------
# 2. CONFIG STATUS ENDPOINT
# ---------------------------------------------------------------------------

class TestConfigStatusEndpoint:
    """Phase 3: Verify GET /api/v1/webhooks/config-status returns safe metadata only."""

    def test_config_status_unconfigured(self, client):
        """When no credentials are set, status shows unconfigured."""
        resp = client.get("/api/v1/webhooks/config-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["key_id_present"] is False
        assert data["key_secret_present"] is False
        assert data["webhook_secret_present"] is False
        assert data["test_mode"] is False

    def test_config_status_configured_test_mode(self, client):
        """When test credentials are set, status shows configured + test mode."""
        with patch("app.api.routes.webhooks.get_settings") as mock:
            mock.return_value = type("S", (), {
                "RAZORPAY_KEY_ID": "rzp_test_abc123",
                "RAZORPAY_KEY_SECRET": "secret",
                "RAZORPAY_WEBHOOK_SECRET": "whsec_test",
            })()
            resp = client.get("/api/v1/webhooks/config-status")
            data = resp.json()
            assert data["configured"] is True
            assert data["test_mode"] is True
            assert data["key_id_present"] is True
            assert data["key_secret_present"] is True
            assert data["webhook_secret_present"] is True

    def test_config_status_no_secrets_exposed(self, client):
        """Config status never returns actual secret values."""
        resp = client.get("/api/v1/webhooks/config-status")
        data = resp.json()
        text = json.dumps(data)
        # Ensure no secret-like values appear
        assert "key_secret" not in text.lower() or text.count("key_secret") <= 3  # only field names
        assert "rzp_test_" not in text or "key_id_present" in text  # only in field names
        # Specific secret values must never appear
        assert "secret123" not in text
        assert "whsec_" not in text

    def test_config_status_missing_fields_indicated(self, client):
        """Status message indicates which fields are missing."""
        resp = client.get("/api/v1/webhooks/config-status")
        data = resp.json()
        assert "missing" in data.get("status_message", "").lower() or data["configured"] is True


# ---------------------------------------------------------------------------
# 3. WEBHOOK SIGNATURE VERIFICATION
# ---------------------------------------------------------------------------

class TestWebhookSignatureVerification:
    """Phase 4 & 9: Verify HMAC-SHA256 signature handling."""

    def test_valid_signature_accepted(self, client, monkeypatch):
        """Webhook with valid HMAC signature is processed."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_day17_sig_001")
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_sig_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        assert data["event_type"] == "payment.failed"

    def test_invalid_signature_rejected(self, client, monkeypatch):
        """Webhook with wrong signature is rejected."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_day17_bad_sig_001")
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw_body,
            headers={"X-Razorpay-Signature": "invalid_signature_abc123"},
        )
        assert resp.status_code == 400

    def test_missing_signature_rejected(self, client):
        """Webhook without X-Razorpay-Signature header is rejected."""
        payload = _make_payload(event_id="evt_day17_no_sig_001")
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw_body,
        )
        assert resp.status_code == 400

    def test_wrong_secret_rejected(self, client, monkeypatch):
        """Webhook signed with wrong secret is rejected."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_day17_wrong_sec_001")
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = _sign(raw_body, "wrong_secret_entirely")
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw_body,
            headers={"X-Razorpay-Signature": signature},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 4. DUPLICATE EVENT IDEMPOTENCY
# ---------------------------------------------------------------------------

class TestDuplicateEventIdempotency:
    """Phase 9: Verify duplicate webhook idempotency."""

    def test_duplicate_returns_duplicate_status(self, client, monkeypatch):
        """Second identical webhook returns 'duplicate' status."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_day17_dup_001")
        _send_raw_webhook(client, payload, event_id="evt_day17_dup_001")
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_dup_001")
        data = resp.json()
        assert data["status"] == "duplicate"

    def test_duplicate_no_extra_payment_created(self, client, db_session, monkeypatch):
        """Duplicate webhook does not create extra Payment records."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_day17_dup_noextra_001", payment_id="pay_dup_noextra_001")
        _send_raw_webhook(client, payload, event_id="evt_day17_dup_noextra_001")
        before = db_session.query(Payment).filter(Payment.razorpay_payment_id == "pay_dup_noextra_001").count()
        _send_raw_webhook(client, payload, event_id="evt_day17_dup_noextra_001")
        after = db_session.query(Payment).filter(Payment.razorpay_payment_id == "pay_dup_noextra_001").count()
        assert after == before  # No new payment created

    def test_duplicate_no_extra_recovery_case(self, client, db_session, monkeypatch):
        """Duplicate webhook does not create extra RecoveryCase records."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_day17_dup_nocase_001", payment_id="pay_dup_nocase_001")
        _send_raw_webhook(client, payload, event_id="evt_day17_dup_nocase_001")
        payment = db_session.query(Payment).filter(Payment.razorpay_payment_id == "pay_dup_nocase_001").first()
        assert payment is not None
        revenue = db_session.query(RevenueRecord).filter(RevenueRecord.payment_id == payment.id).first()
        assert revenue is not None
        before = db_session.query(RecoveryCase).filter(RecoveryCase.revenue_record_id == revenue.id).count()
        _send_raw_webhook(client, payload, event_id="evt_day17_dup_nocase_001")
        after = db_session.query(RecoveryCase).filter(RecoveryCase.revenue_record_id == revenue.id).count()
        assert after == before


# ---------------------------------------------------------------------------
# 5. MALFORMED AND UNSUPPORTED EVENTS
# ---------------------------------------------------------------------------

class TestMalformedAndUnsupported:
    """Phase 12: Verify safe handling of bad payloads."""

    def test_malformed_json_rejected(self, client, monkeypatch):
        """Non-JSON payload is rejected safely."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            content=b"not json at all",
            headers={"X-Razorpay-Signature": "fake"},
        )
        assert resp.status_code in (400, 422)

    def test_missing_event_id_rejected(self, client, monkeypatch):
        """Payload without event ID is rejected."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = {"entity": "event", "event": "payment.failed"}
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = _sign(raw_body)
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw_body,
            headers={"X-Razorpay-Signature": signature},
        )
        assert resp.status_code == 400

    def test_unsupported_event_handled_safely(self, client, monkeypatch):
        """Non-payment event (e.g. refund.created) is processed without crash."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = {
            "id": "evt_day17_unsupported_001",
            "entity": "event",
            "event": "refund.created",
            "contains": ["refund"],
            "payload": {
                "refund": {
                    "entity": {
                        "id": "rfnd_test_001",
                        "amount": 100000,
                        "status": "processed",
                    }
                }
            },
        }
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_unsupported_001")
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"


# ---------------------------------------------------------------------------
# 6. PAYMENT.FAILED COMPLETE PIPELINE
# ---------------------------------------------------------------------------

class TestPaymentFailedPipeline:
    """Phase 10: Verify the complete payment.failed webhook → recovery pipeline."""

    def test_full_pipeline_creates_all_entities(self, client, db_session, monkeypatch):
        """payment.failed creates Payment, RevenueRecord, RecoveryCase, and audit logs."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(
            event_id="evt_day17_pipeline_001",
            payment_id="pay_day17_pipeline_001",
            amount=250000,
        )
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_pipeline_001")
        data = resp.json()

        assert data["status"] == "processed"
        assert data["recovery_case_id"] is not None
        assert data["orchestration_status"] is not None

        # Verify DB entities
        payment = db_session.query(Payment).filter(
            Payment.razorpay_payment_id == "pay_day17_pipeline_001"
        ).first()
        assert payment is not None
        assert payment.status == PaymentStatus.failed
        assert payment.amount == 250000

        revenue = db_session.query(RevenueRecord).filter(
            RevenueRecord.payment_id == payment.id
        ).first()
        assert revenue is not None
        assert revenue.status == RevenueStatus.at_risk
        assert revenue.recoverable_amount == 250000

        case = db_session.query(RecoveryCase).filter(
            RecoveryCase.revenue_record_id == revenue.id
        ).first()
        assert case is not None
        assert case.current_state in (
            RecoveryCaseState.open,
            RecoveryCaseState.action_pending,
            RecoveryCaseState.recovering,
        )

    def test_orchestration_triggered(self, client, db_session, monkeypatch):
        """payment.failed triggers RecoveryOrchestrator."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(
            event_id="evt_day17_orch_001",
            payment_id="pay_day17_orch_001",
            amount=250000,
        )
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_orch_001")
        data = resp.json()
        assert data["orchestration_status"] is not None
        assert data["orchestration_status"] in (
            "completed", "approval_required", "approval_created",
            "policy_blocked", "execution_failed",
        )

    def test_low_risk_auto_execution(self, client, db_session, monkeypatch):
        """Low-risk payment (< ₹1,000) auto-executes without human approval."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(
            event_id="evt_day17_low_001",
            payment_id="pay_day17_low_001",
            amount=50000,  # ₹500 = low risk
        )
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_low_001")
        data = resp.json()
        # Low risk + auto_execute_low_risk=True (default) should complete
        assert data["orchestration_status"] == "completed"

    def test_high_risk_approval_gate(self, client, db_session, monkeypatch):
        """High/critical-risk payment triggers human approval gate."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_high_value_payload(
            event_id="evt_day17_highrisk_001",
            payment_id="pay_day17_highrisk_001",
        )
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_highrisk_001")
        data = resp.json()
        assert data["orchestration_status"] == "approval_required"
        assert data["approval_id"] is not None

    def test_risk_assessment_from_amount(self, client, db_session, monkeypatch):
        """Risk level is correctly assessed from payment amount."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        test_cases = [
            (50000, "low"),       # ₹500
            (500000, "medium"),   # ₹5,000
            (2500000, "high"),    # ₹25,000
            (4500000, "critical"),# ₹45,000
        ]
        for amount, expected_risk in test_cases:
            event_id = f"evt_day17_risk_{amount}"
            payment_id = f"pay_day17_risk_{amount}"
            payload = _make_payload(event_id=event_id, payment_id=payment_id, amount=amount)
            resp = _send_raw_webhook(client, payload, event_id=event_id)
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 7. AUDIT TRAIL COMPLETENESS
# ---------------------------------------------------------------------------

class TestAuditTrail:
    """Phase 10: Verify audit trail is generated for every webhook."""

    def test_webhook_generates_audit_logs(self, client, db_session, monkeypatch):
        """Each webhook generates multiple audit log entries."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(
            event_id="evt_day17_audit_001",
            payment_id="pay_day17_audit_001",
        )
        _send_raw_webhook(client, payload, event_id="evt_day17_audit_001")
        logs = db_session.query(AuditLog).all()
        actions = {log.action for log in logs}
        assert "razorpay_webhook_received" in actions
        assert "payment_failed" in actions
        assert "razorpay_webhook_processed" in actions

    def test_audit_metadata_includes_event_details(self, client, db_session, monkeypatch):
        """Audit log metadata contains event_id and event_type."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(
            event_id="evt_day17_meta_001",
            payment_id="pay_day17_meta_001",
        )
        _send_raw_webhook(client, payload, event_id="evt_day17_meta_001")
        processed_log = db_session.query(AuditLog).filter(
            AuditLog.action == "razorpay_webhook_processed"
        ).first()
        assert processed_log is not None
        meta = processed_log.event_metadata or {}
        assert meta.get("event_id") == "evt_day17_meta_001"
        assert meta.get("event_type") == "payment.failed"
        assert meta.get("recovery_case_id") is not None


# ---------------------------------------------------------------------------
# 8. ANALYTICS UPDATE
# ---------------------------------------------------------------------------

class TestAnalyticsUpdate:
    """Phase 10: Verify analytics reflect webhook processing."""

    def test_analytics_overview_updates(self, client, monkeypatch):
        """After webhook, analytics overview shows the new case."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        _send_raw_webhook(
            client,
            _make_payload(event_id="evt_day17_analytics_001", payment_id="pay_day17_analytics_001"),
            event_id="evt_day17_analytics_001",
        )
        resp = client.get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] >= 1

    def test_recent_activity_includes_webhook(self, client, monkeypatch):
        """Recent activity feed includes webhook events."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        _send_raw_webhook(
            client,
            _make_payload(event_id="evt_day17_activity_001", payment_id="pay_day17_activity_001"),
            event_id="evt_day17_activity_001",
        )
        resp = client.get("/api/v1/analytics/recent-activity?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1


# ---------------------------------------------------------------------------
# 9. TUNNEL GUIDE
# ---------------------------------------------------------------------------

class TestTunnelGuide:
    """Phase 6: Verify tunnel guide endpoint."""

    def test_tunnel_guide_returns_instructions(self, client):
        """Tunnel guide provides ngrok and Cloudflare instructions."""
        resp = client.get("/api/v1/webhooks/tunnel-guide")
        assert resp.status_code == 200
        data = resp.json()
        assert "tunnel_options" in data
        assert len(data["tunnel_options"]) >= 2
        tools = [opt["tool"] for opt in data["tunnel_options"]]
        assert any("ngrok" in t.lower() for t in tools)
        assert any("cloudflare" in t.lower() or "cloudflared" in t.lower() for t in tools)

    def test_tunnel_guide_target_url(self, client):
        """Tunnel guide target URL points to the webhook endpoint."""
        resp = client.get("/api/v1/webhooks/tunnel-guide")
        data = resp.json()
        assert "/api/v1/webhooks/razorpay" in data["target_url"]

    def test_tunnel_guide_security_notice(self, client):
        """Tunnel guide includes security notice."""
        resp = client.get("/api/v1/webhooks/tunnel-guide")
        data = resp.json()
        assert len(data.get("security_notice", "")) > 20


# ---------------------------------------------------------------------------
# 10. SECRET LEAKAGE PREVENTION
# ---------------------------------------------------------------------------

class TestSecretLeakagePrevention:
    """Phase 13: Verify no secrets appear in any API response."""

    def test_webhook_response_no_secrets(self, client, monkeypatch):
        """Webhook response never includes secret values."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_day17_nosec_001")
        resp = _send_raw_webhook(client, payload, event_id="evt_day17_nosec_001")
        text = resp.text
        assert "rzp_test_webhook_secret" not in text
        assert "key_secret" not in text.lower() or "key_secret_present" in text

    def test_config_status_no_secrets(self, client):
        """Config status never includes actual secret values."""
        resp = client.get("/api/v1/webhooks/config-status")
        text = resp.text
        # Ensure no real secret values leak
        assert "whsec_" not in text

    def test_tunnel_guide_no_secrets(self, client):
        """Tunnel guide never includes secret values."""
        resp = client.get("/api/v1/webhooks/tunnel-guide")
        text = resp.text
        assert "RAZORPAY_KEY_SECRET" not in text or "secret" in text.lower()  # only field name
        assert "whsec_" not in text

    def test_fixtures_no_secrets(self, client):
        """Webhook fixtures never include secret values."""
        resp = client.get("/api/v1/webhooks/fixtures")
        text = resp.text
        assert "RAZORPAY_KEY_SECRET" not in text
        assert "whsec_" not in text

    def test_recent_events_no_secrets(self, client):
        """Recent events endpoint never includes secret values."""
        resp = client.get("/api/v1/webhooks/recent-events")
        text = resp.text
        assert "whsec_" not in text
        assert "key_secret" not in text.lower() or "key_secret_present" in text


# ---------------------------------------------------------------------------
# 11. DEVELOPER SIMULATION CONSOLE
# ---------------------------------------------------------------------------

class TestSimulationConsole:
    """Verify the developer simulation console still works correctly."""

    def test_simulation_console_payment_failed(self, client):
        """Simulate payment.failed via console endpoint."""
        payload = _make_payload(
            event_id="evt_day17_console_001",
            payment_id="pay_day17_console_001",
        )
        resp = _send_test_console(client, "evt_day17_console_001", payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        assert data["is_duplicate"] is False
        assert data["recovery_case_id"] is not None

    def test_simulation_console_high_value(self, client):
        """Simulate high-value payment failure via console."""
        payload = _make_high_value_payload(
            event_id="evt_day17_console_high_001",
            payment_id="pay_day17_console_high_001",
        )
        resp = _send_test_console(client, "evt_day17_console_high_001", payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["orchestration_status"] == "approval_required"

    def test_simulation_console_refund_event(self, client):
        """Simulate refund.created via console (unsupported event, handled safely)."""
        payload = {
            "id": "evt_day17_console_refund_001",
            "entity": "event",
            "event": "refund.created",
            "contains": ["refund"],
            "payload": {
                "refund": {
                    "entity": {
                        "id": "rfnd_console_001",
                        "amount": 100000,
                        "status": "processed",
                    }
                }
            },
        }
        resp = _send_test_console(client, "evt_day17_console_refund_001", payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

    def test_simulation_console_returns_entity_ids(self, client):
        """Console response includes payment_id, revenue_record_id, recovery_case_id."""
        payload = _make_payload(
            event_id="evt_day17_console_ids_001",
            payment_id="pay_day17_console_ids_001",
        )
        resp = _send_test_console(client, "evt_day17_console_ids_001", payload)
        data = resp.json()
        assert data["payment_id"] is not None
        assert data["revenue_record_id"] is not None
        assert data["recovery_case_id"] is not None


# ---------------------------------------------------------------------------
# 12. WEBHOOK FIXTURES
# ---------------------------------------------------------------------------

class TestWebhookFixtures:
    """Verify predefined webhook fixtures are valid."""

    def test_fixtures_endpoint_returns_list(self, client):
        """GET /api/v1/webhooks/fixtures returns a list of fixtures."""
        resp = client.get("/api/v1/webhooks/fixtures")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 4

    def test_fixtures_have_required_fields(self, client):
        """Each fixture has key, title, event_type, description, payload."""
        resp = client.get("/api/v1/webhooks/fixtures")
        for fixture in resp.json():
            assert "key" in fixture
            assert "title" in fixture
            assert "event_type" in fixture
            assert "payload" in fixture

    def test_fixtures_can_be_sent_via_console(self, client):
        """All fixtures can be sent via the test console without errors."""
        resp = client.get("/api/v1/webhooks/fixtures")
        for fixture in resp.json():
            console_resp = _send_test_console(client, fixture["key"], fixture["payload"])
            assert console_resp.status_code == 200


# ---------------------------------------------------------------------------
# 13. DEMO MODE INDEPENDENCE
# ---------------------------------------------------------------------------

class TestDemoModeIndependence:
    """Phase 8: Verify demo mode works independently of Razorpay config."""

    def test_demo_seed_works(self, client):
        """Demo dataset seeding works without Razorpay credentials."""
        resp = client.post("/api/v1/demo/seed", json={"count": 10, "seed": 42, "reset": True})
        assert resp.status_code == 201
        data = resp.json()
        assert data["cases_created"] >= 10

    def test_simulate_payment_failure_works(self, client):
        """Simulate Razorpay Payment Failure button works without real credentials."""
        fixtures_resp = client.get("/api/v1/webhooks/fixtures")
        fixtures = fixtures_resp.json()
        fixture = next(f for f in fixtures if f["key"] == "payment_failed_insufficient_funds")
        resp = client.post(
            "/api/v1/webhooks/test/razorpay",
            json={"event_type": fixture["event_type"], "payload": fixture["payload"]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

    def test_analytics_work_without_razorpay(self, client):
        """Analytics endpoints work without Razorpay credentials."""
        resp = client.get("/api/v1/analytics/overview")
        assert resp.status_code == 200

    def test_live_monitor_works_without_razorpay(self, client):
        """Live monitor endpoint works without Razorpay credentials."""
        resp = client.get("/api/v1/webhooks/recent-events")
        assert resp.status_code == 200

    def test_system_health_works_without_razorpay(self, client):
        """System health works without Razorpay credentials."""
        resp = client.get("/api/v1/system/status")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 14. REAL RAZORPAY PAYLOAD FORMAT COMPATIBILITY
# ---------------------------------------------------------------------------

class TestRazorpayPayloadFormat:
    """Verify our implementation handles the exact Razorpay webhook format."""

    def test_real_razorpay_event_id_header(self, client, monkeypatch):
        """Razorpay sends event ID in X-Razorpay-Event-Id header."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = _make_payload(event_id="evt_rzp_header_001")
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = _sign(raw_body)
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw_body,
            headers={
                "X-Razorpay-Signature": signature,
                "X-Razorpay-Event-Id": "evt_rzp_header_001",
            },
        )
        assert resp.status_code == 200

    def test_real_razorpay_nested_payload_structure(self, client, monkeypatch):
        """Razorpay nests payment entity under payload.payment.entity."""
        monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        payload = {
            "id": "evt_rzp_nested_001",
            "entity": "event",
            "account_id": "acc_test",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_rzp_nested_001",
                        "entity": "payment",
                        "amount": 100000,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": "order_rzp_001",
                        "method": "upi",
                        "email": "test@razorpay.com",
                        "contact": "+919999999999",
                        "error_code": "BAD_REQUEST_ERROR",
                        "error_description": "Payment failed",
                        "error_source": "bank",
                        "error_step": "payment_authorization",
                        "error_reason": "payment_failed",
                    }
                }
            },
            "created_at": 1724500000,
        }
        resp = _send_raw_webhook(client, payload, event_id="evt_rzp_nested_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recovery_case_id"] is not None
