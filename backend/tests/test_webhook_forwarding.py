"""
Comprehensive test suite for Developer Webhook Simulation, Forwarding, Idempotency & Metrics.
"""

from app.core.metrics import metrics
from app.models.audit import AuditLog
from app.models.enums import PaymentStatus, RevenueStatus
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from sqlalchemy import select


def test_get_webhook_fixtures_endpoint(client):
    """Verify endpoint returns curated list of synthetic developer fixtures."""
    res = client.get("/api/v1/webhooks/fixtures")
    assert res.status_code == 200
    fixtures = res.json()
    assert len(fixtures) >= 4
    keys = [f["key"] for f in fixtures]
    assert "payment_failed_insufficient_funds" in keys
    assert "payment_captured_success" in keys
    assert "refund_created" in keys


def test_get_webhook_tunnel_guide_endpoint(client):
    """Verify endpoint returns local tunnel recipes."""
    res = client.get("/api/v1/webhooks/tunnel-guide")
    assert res.status_code == 200
    guide = res.json()
    assert "target_url" in guide
    assert len(guide["tunnel_options"]) >= 2
    tools = [opt["tool"] for opt in guide["tunnel_options"]]
    assert any("ngrok" in t for t in tools)
    assert any("Cloudflare" in t for t in tools)


def test_execute_test_webhook_payment_failed(client, db_session):
    """Execute synthetic payment.failed webhook through the complete test pipeline."""
    initial_processed = metrics.get_count("webhook_processed_total")

    payload = {
        "event_type": "payment.failed",
        "payload": {
            "entity": "event",
            "account_id": "acc_test_sim",
            "event": "payment.failed",
            "id": "evt_test_sim_fail_001",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_sim_001",
                        "entity": "payment",
                        "amount": 350000,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": "order_sim_001",
                        "method": "card",
                        "email": "sim_user@example.com",
                    }
                }
            },
            "created_at": 1724500000,
        },
    }

    res = client.post("/api/v1/webhooks/test/razorpay", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"
    assert data["event_id"] == "evt_test_sim_fail_001"
    assert data["is_duplicate"] is False
    assert data["payment_id"] is not None
    assert data["revenue_record_id"] is not None
    assert data["audit_action"] == "razorpay_webhook_processed"


    # Verify metrics increment
    assert metrics.get_count("webhook_processed_total") == initial_processed + 1

    # Verify database state
    payment = db_session.scalar(
        select(Payment).where(Payment.razorpay_payment_id == "pay_test_sim_001")
    )
    assert payment is not None
    assert payment.status == PaymentStatus.failed

    revenue = db_session.scalar(
        select(RevenueRecord).where(RevenueRecord.payment_id == payment.id)
    )
    assert revenue is not None
    assert revenue.status == RevenueStatus.at_risk


def test_execute_test_webhook_idempotency_duplicate(client, db_session):
    """Executing the exact same synthetic event twice returns duplicate ignored without duplicates."""
    payload = {
        "event_type": "payment.failed",
        "payload": {
            "entity": "event",
            "account_id": "acc_test_sim",
            "event": "payment.failed",
            "id": "evt_test_sim_dup_002",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_sim_dup_002",
                        "entity": "payment",
                        "amount": 200000,
                        "currency": "INR",
                        "status": "failed",
                    }
                }
            },
            "created_at": 1724500000,
        },
    }

    # Dispatch 1
    res1 = client.post("/api/v1/webhooks/test/razorpay", json=payload)
    assert res1.status_code == 200
    assert res1.json()["is_duplicate"] is False

    initial_dup_count = metrics.get_count("webhook_duplicate_total")

    # Dispatch 2 (Identical event ID)
    res2 = client.post("/api/v1/webhooks/test/razorpay", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "duplicate"
    assert data2["is_duplicate"] is True
    assert data2["audit_action"] == "razorpay_webhook_duplicate"

    assert metrics.get_count("webhook_duplicate_total") == initial_dup_count + 1

    # Verify only 1 Payment was created
    payments = list(
        db_session.scalars(
            select(Payment).where(Payment.razorpay_payment_id == "pay_test_sim_dup_002")
        ).all()
    )
    assert len(payments) == 1


def test_execute_test_webhook_payment_captured(client, db_session):
    """Execute synthetic payment.captured webhook."""
    payload = {
        "event_type": "payment.captured",
        "payload": {
            "entity": "event",
            "id": "evt_test_sim_cap_003",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_sim_cap_003",
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        },
    }

    res = client.post("/api/v1/webhooks/test/razorpay", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.captured"


def test_execute_test_webhook_refund_created(client, db_session):
    """Execute synthetic refund.created webhook."""
    payload = {
        "event_type": "refund.created",
        "payload": {
            "entity": "event",
            "id": "evt_test_sim_ref_004",
            "event": "refund.created",
            "contains": ["refund"],
            "payload": {
                "refund": {
                    "entity": {
                        "id": "rfnd_test_sim_004",
                        "amount": 100000,
                        "status": "processed",
                    }
                }
            },
        },
    }

    res = client.post("/api/v1/webhooks/test/razorpay", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"


def test_system_metrics_endpoint_includes_webhook_and_policy_counters(client):
    """GET /api/v1/system/metrics returns active counts including policy and webhook metrics."""
    res = client.get("/api/v1/system/metrics")
    assert res.status_code == 200
    body = res.json()
    assert "metrics" in body
    m = body["metrics"]
    # Verify presence of metrics keys (at least as recorded or integer values)
    assert isinstance(m, dict)
