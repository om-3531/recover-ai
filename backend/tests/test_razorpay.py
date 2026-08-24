"""
Tests for Razorpay Integration, Signature Verification, and Webhook Ingestion.

Covers:
- HMAC SHA-256 signature verification (payment & webhook)
- Razorpay order creation (mocked external API)
- Webhook signature verification, idempotency deduplication, and error handling
- Payment and Revenue state transitions from webhook events (payment.captured, payment.failed)
- Unsupported webhook events safe handling
- Audit logging for all integration operations
"""

import hashlib
import hmac
import json
import pytest
from unittest.mock import MagicMock, patch

from app.core.config import get_settings
from app.integrations.razorpay.client import RazorpayClient
from app.integrations.razorpay.exceptions import (
    RazorpayConfigurationError,
    RazorpayOrderCreationError,
    RazorpaySignatureVerificationError,
)
from app.integrations.razorpay.service import RazorpayService
from app.integrations.razorpay.signature import (
    verify_payment_signature,
    verify_webhook_signature,
)
from app.models.enums import PaymentStatus, RevenueStatus
from app.models.payment import Payment, PaymentEvent
from app.models.revenue import RevenueRecord
from app.services.audit_service import AuditService

TEST_KEY_ID = "rzp_test_mock_key_id"
TEST_KEY_SECRET = "mock_secret_key_12345"
TEST_WEBHOOK_SECRET = "mock_webhook_secret_67890"


def generate_payment_signature(order_id: str, payment_id: str, secret: str = TEST_KEY_SECRET) -> str:
    """Helper to generate a valid test payment signature."""
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def generate_webhook_signature(payload_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Helper to generate a valid test webhook signature."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# 1. SIGNATURE VERIFICATION TESTS
# ---------------------------------------------------------------------------


def test_payment_signature_verification_success_and_failure():
    """Verify payment signature verification logic."""
    order_id = "order_test_123"
    payment_id = "pay_test_456"
    valid_sig = generate_payment_signature(order_id, payment_id, TEST_KEY_SECRET)

    # Valid signature
    assert verify_payment_signature(order_id, payment_id, valid_sig, TEST_KEY_SECRET) is True

    # Invalid signature
    assert verify_payment_signature(order_id, payment_id, "invalid_sig_abc", TEST_KEY_SECRET) is False

    # Wrong secret
    assert verify_payment_signature(order_id, payment_id, valid_sig, "wrong_secret") is False

    # Missing inputs
    assert verify_payment_signature("", payment_id, valid_sig, TEST_KEY_SECRET) is False
    assert verify_payment_signature(order_id, "", valid_sig, TEST_KEY_SECRET) is False
    assert verify_payment_signature(order_id, payment_id, "", TEST_KEY_SECRET) is False
    assert verify_payment_signature(order_id, payment_id, valid_sig, "") is False


def test_webhook_signature_verification_success_and_failure():
    """Verify webhook HMAC signature verification logic."""
    raw_payload = b'{"event":"payment.captured","id":"evt_test_1"}'
    valid_sig = generate_webhook_signature(raw_payload, TEST_WEBHOOK_SECRET)

    # Valid webhook signature
    assert verify_webhook_signature(raw_payload, valid_sig, TEST_WEBHOOK_SECRET) is True

    # Invalid webhook signature
    assert verify_webhook_signature(raw_payload, "tampered_sig", TEST_WEBHOOK_SECRET) is False

    # Tampered body
    tampered_payload = b'{"event":"payment.captured","id":"evt_test_1","extra":1}'
    assert verify_webhook_signature(tampered_payload, valid_sig, TEST_WEBHOOK_SECRET) is False

    # Missing inputs
    assert verify_webhook_signature(b"", valid_sig, TEST_WEBHOOK_SECRET) is False
    assert verify_webhook_signature(raw_payload, "", TEST_WEBHOOK_SECRET) is False


# ---------------------------------------------------------------------------
# 2. CLIENT & CONFIGURATION TESTS
# ---------------------------------------------------------------------------


def test_razorpay_client_missing_config():
    """Verify client raises configuration error when keys are missing."""
    client = RazorpayClient(key_id="", key_secret="")
    with pytest.raises(RazorpayConfigurationError):
        client.create_order(amount=50000)


def test_razorpay_client_create_order_success():
    """Verify client successfully sends order creation request with mocked HTTP response."""
    client = RazorpayClient(key_id=TEST_KEY_ID, key_secret=TEST_KEY_SECRET)

    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.json.return_value = {
        "id": "order_mock_001",
        "amount": 49900,
        "currency": "INR",
        "status": "created",
        "receipt": "rcpt_001",
        "created_at": 1718000000,
    }

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        order = client.create_order(amount=49900, currency="INR", receipt="rcpt_001")
        assert order["id"] == "order_mock_001"
        assert order["amount"] == 49900
        mock_post.assert_called_once()


def test_razorpay_client_invalid_amount():
    """Verify client rejects non-positive amounts."""
    client = RazorpayClient(key_id=TEST_KEY_ID, key_secret=TEST_KEY_SECRET)
    with pytest.raises(ValueError):
        client.create_order(amount=0)
    with pytest.raises(ValueError):
        client.create_order(amount=-100)


# ---------------------------------------------------------------------------
# 3. REST API: ORDERS & SIGNATURE VERIFICATION
# ---------------------------------------------------------------------------


def test_api_create_razorpay_order(client):
    """Test POST /api/v1/payments/orders creates order via mocked integration client."""
    mock_order = {
        "id": "order_api_test_001",
        "amount": 75000,
        "currency": "INR",
        "status": "created",
        "receipt": "rcpt_test_101",
        "created_at": 1718000000,
    }

    with patch.object(RazorpayClient, "create_order", return_value=mock_order):
        resp = client.post(
            "/api/v1/payments/orders",
            json={
                "amount": 75000,
                "currency": "INR",
                "receipt": "rcpt_test_101",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "order_api_test_001"
        assert data["amount"] == 75000
        assert data["currency"] == "INR"


def test_api_verify_payment_signature(client, monkeypatch):
    """Test POST /api/v1/payments/verify-signature."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_KEY_SECRET", TEST_KEY_SECRET)

    order_id = "order_chk_001"
    payment_id = "pay_chk_001"
    valid_sig = generate_payment_signature(order_id, payment_id, TEST_KEY_SECRET)

    # 1. Valid signature -> 200 OK
    resp_valid = client.post(
        "/api/v1/payments/verify-signature",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": valid_sig,
        },
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["verified"] is True

    # 2. Invalid signature -> 400 Bad Request
    resp_invalid = client.post(
        "/api/v1/payments/verify-signature",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": "fraudulent_signature",
        },
    )
    assert resp_invalid.status_code == 400
    assert "Invalid Razorpay signature" in resp_invalid.json()["detail"]


# ---------------------------------------------------------------------------
# 4. WEBHOOK INGESTION, IDEMPOTENCY & STATE SYNCHRONIZATION
# ---------------------------------------------------------------------------


def test_webhook_missing_or_invalid_signature(client, monkeypatch):
    """Test webhook endpoint rejects requests with missing or invalid signatures."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    payload = json.dumps({"id": "evt_sig_test", "event": "payment.captured"}).encode("utf-8")

    # Missing header -> 400 Bad Request
    resp_missing = client.post(
        "/api/v1/webhooks/razorpay",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert resp_missing.status_code == 400
    assert "Missing X-Razorpay-Signature" in resp_missing.json()["detail"]

    # Invalid header -> 400 Bad Request
    resp_invalid = client.post(
        "/api/v1/webhooks/razorpay",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_sig",
        },
    )
    assert resp_invalid.status_code == 400
    assert "Invalid Razorpay webhook signature" in resp_invalid.json()["detail"]


def test_webhook_payment_captured_success_and_idempotency(client, db_session, monkeypatch):
    """
    Test payment.captured webhook:
    1. Creates Payment and RevenueRecord (recognized)
    2. Repeated delivery returns idempotent response without duplicates
    """
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload_dict = {
        "entity": "event",
        "account_id": "acc_test_101",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_hook_cap_001",
                    "order_id": "order_hook_001",
                    "amount": 125000,  # 1,250.00 INR
                    "currency": "INR",
                    "status": "captured",
                    "method": "card",
                    "email": "payer@example.com",
                    "contact": "+919876543210",
                }
            }
        },
        "id": "evt_cap_unique_001",
        "created_at": 1718000000,
    }
    raw_payload = json.dumps(payload_dict).encode("utf-8")
    sig = generate_webhook_signature(raw_payload, TEST_WEBHOOK_SECRET)

    # First delivery -> 200 OK, processed
    resp1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "processed"
    assert data1["event_id"] == "evt_cap_unique_001"

    # Verify Payment and RevenueRecord in DB
    payment = db_session.query(Payment).filter_by(razorpay_payment_id="pay_hook_cap_001").first()
    assert payment is not None
    assert payment.status == PaymentStatus.captured
    assert payment.amount == 125000

    revenue = db_session.query(RevenueRecord).filter_by(payment_id=payment.id).first()
    assert revenue is not None
    assert revenue.status == RevenueStatus.recognized
    assert revenue.recoverable_amount == 0

    # Second delivery with identical event ID -> 200 OK, duplicate ignored
    resp2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "duplicate"
    assert data2["event_id"] == "evt_cap_unique_001"

    # Confirm no duplicate payment or revenue rows created
    payment_count = db_session.query(Payment).filter_by(razorpay_payment_id="pay_hook_cap_001").count()
    assert payment_count == 1
    event_count = db_session.query(PaymentEvent).filter_by(razorpay_event_id="evt_cap_unique_001").count()
    assert event_count == 1


def test_webhook_payment_failed_state_and_revenue_at_risk(client, db_session, monkeypatch):
    """
    Test payment.failed webhook marks payment failed and creates RevenueRecord as at_risk.
    """
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload_dict = {
        "entity": "event",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_hook_fail_001",
                    "order_id": "order_fail_001",
                    "amount": 349900,  # 3,499.00 INR
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "email": "failed_cust@example.com",
                }
            }
        },
        "id": "evt_fail_unique_001",
    }
    raw_payload = json.dumps(payload_dict).encode("utf-8")
    sig = generate_webhook_signature(raw_payload, TEST_WEBHOOK_SECRET)

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    # Verify payment is failed and revenue is marked at_risk
    payment = db_session.query(Payment).filter_by(razorpay_payment_id="pay_hook_fail_001").first()
    assert payment is not None
    assert payment.status == PaymentStatus.failed

    revenue = db_session.query(RevenueRecord).filter_by(payment_id=payment.id).first()
    assert revenue is not None
    assert revenue.status == RevenueStatus.at_risk
    assert revenue.recoverable_amount == 349900

    # Verify audit trail entries
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="payment", entity_id=str(payment.id)
    )
    assert total >= 1
    assert any(a.action == "payment_failed" for a in audits)


def test_webhook_unsupported_event_safe_handling(client, db_session, monkeypatch):
    """
    Test unsupported events (e.g. order.paid, refund.speed_changed) are recorded safely
    without crashing or corrupting database records.
    """
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload_dict = {
        "entity": "event",
        "event": "order.paid",
        "contains": ["order"],
        "payload": {
            "order": {
                "entity": {
                    "id": "order_unsupported_001",
                    "amount": 50000,
                }
            }
        },
        "id": "evt_unsupported_001",
    }
    raw_payload = json.dumps(payload_dict).encode("utf-8")
    sig = generate_webhook_signature(raw_payload, TEST_WEBHOOK_SECRET)

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert resp.json()["event_type"] == "order.paid"

    # Event persisted in DB
    event = db_session.query(PaymentEvent).filter_by(razorpay_event_id="evt_unsupported_001").first()
    assert event is not None
    assert event.event_type == "order.paid"


def test_webhook_malformed_payload_and_missing_id(client, monkeypatch):
    """Test webhook endpoint handles malformed payloads or missing event IDs."""
    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # 1. Invalid JSON
    bad_json = b"not a json string"
    sig1 = generate_webhook_signature(bad_json, TEST_WEBHOOK_SECRET)
    resp1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=bad_json,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig1},
    )
    assert resp1.status_code == 400
    assert "Malformed JSON payload" in resp1.json()["detail"]

    # 2. Missing event ID
    missing_id_json = json.dumps({"event": "payment.captured"}).encode("utf-8")
    sig2 = generate_webhook_signature(missing_id_json, TEST_WEBHOOK_SECRET)
    resp2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=missing_id_json,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig2},
    )
    assert resp2.status_code == 400
    assert "Missing event ID" in resp2.json()["detail"]
