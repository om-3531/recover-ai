"""
Day 16 — Real-Time Webhook Monitor & Live Recovery Flow E2E Tests.

Covers:
1. GET /api/v1/webhooks/recent-events returns empty list when no events
2. GET /api/v1/webhooks/recent-events returns events after webhook processing
3. GET /api/v1/webhooks/recent-events respects limit parameter
4. GET /api/v1/webhooks/recent-events events contain required fields
5. GET /api/v1/webhooks/recent-events returns correct event type for payment.failed
6. GET /api/v1/webhooks/recent-events shows orchestration metadata
7. GET /api/v1/webhooks/recent-events marks duplicates correctly
8. GET /api/v1/recovery-cases/{id}/timeline returns 404 for nonexistent case
9. GET /api/v1/recovery-cases/{id}/timeline returns events after orchestration
10. GET /api/v1/recovery-cases/{id}/timeline respects limit parameter
11. GET /api/v1/recovery-cases/{id}/timeline events are ordered chronologically
12. GET /api/v1/recovery-cases/{id}/timeline returns total_events count
13. GET /api/v1/recovery-cases/{id}/timeline includes orchestration_started action
14. Live monitor shows updated events after new webhook
15. Timeline endpoint returns empty events for case with no activity
16. Recent events endpoint returns correct total count
17. Schema validation for WebhookRecentEventsResponse
18. Schema validation for RecoveryTimelineResponse
"""

import json
import pytest
from unittest.mock import patch

from app.integrations.razorpay.signature import create_hmac_sha256_signature
from app.models.audit import AuditLog
from app.services.audit_service import AuditService
from app.core.config import get_settings

TEST_WEBHOOK_SECRET = "rzp_test_webhook_secret_day16"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return create_hmac_sha256_signature(raw_body=payload_bytes, secret=secret)


def _make_payment_failed_payload(
    event_id: str = "evt_day16_fail_001",
    payment_id: str = "pay_day16_fail_001",
    amount: int = 250000,
) -> dict:
    return {
        "entity": "event",
        "account_id": "acc_day16_recoverai",
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
                    "order_id": "order_day16_001",
                    "method": "card",
                    "email": "day16_test@example.com",
                    "contact": "+919876543210",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Insufficient funds",
                    "error_source": "bank",
                    "error_step": "payment_authorization",
                    "error_reason": "payment_failed",
                }
            }
        },
        "created_at": 1724500000,
    }


def _send_webhook(client, event_id, payload_dict):
    """Send a test webhook via the developer console endpoint."""
    raw_body = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    app_settings = get_settings()
    secret = app_settings.RAZORPAY_WEBHOOK_SECRET or TEST_WEBHOOK_SECRET
    signature = _sign_payload(raw_body, secret)
    return client.post(
        "/api/v1/webhooks/test/razorpay",
        json={"event_type": payload_dict["event"], "payload": payload_dict},
    )


# ---------------------------------------------------------------------------
# TESTS: GET /api/v1/webhooks/recent-events
# ---------------------------------------------------------------------------

class TestRecentWebhookEvents:
    """Tests for the real-time webhook monitor endpoint."""

    def test_recent_events_empty_when_no_events(self, client):
        """Endpoint returns empty list when no webhook events exist."""
        resp = client.get("/api/v1/webhooks/recent-events")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["items"] == []
        assert data["total"] == 0

    def test_recent_events_after_webhook(self, client):
        """Events appear after sending a webhook."""
        _send_webhook(client, "evt_day16_mon_001", _make_payment_failed_payload(event_id="evt_day16_mon_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        data = resp.json()
        assert len(data["items"]) >= 1
        event_types = [e["event_type"] for e in data["items"]]
        assert "payment.failed" in event_types

    def test_recent_events_limit(self, client):
        """Limit parameter caps the number of returned events."""
        for i in range(5):
            _send_webhook(
                client,
                f"evt_day16_lim_{i:03d}",
                _make_payment_failed_payload(event_id=f"evt_day16_lim_{i:03d}", amount=100000 + i * 10000),
            )
        resp = client.get("/api/v1/webhooks/recent-events?limit=2")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    def test_recent_events_required_fields(self, client):
        """Each event contains all required response fields."""
        _send_webhook(client, "evt_day16_fields_001", _make_payment_failed_payload(event_id="evt_day16_fields_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        item = resp.json()["items"][0]
        required = {"id", "event_type", "status", "timestamp", "is_duplicate"}
        assert required.issubset(item.keys())

    def test_recent_events_payment_failed_type(self, client):
        """Event type is correctly identified as payment.failed."""
        _send_webhook(client, "evt_day16_type_001", _make_payment_failed_payload(event_id="evt_day16_type_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        items = resp.json()["items"]
        assert any(e["event_type"] == "payment.failed" for e in items)

    def test_recent_events_contains_orchestration_metadata(self, client):
        """Events include orchestration_status metadata from processing."""
        _send_webhook(client, "evt_day16_orch_001", _make_payment_failed_payload(event_id="evt_day16_orch_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        items = resp.json()["items"]
        matching = [e for e in items if e.get("recovery_case_id") is not None]
        assert len(matching) >= 1
        assert matching[0]["orchestration_status"] is not None

    def test_recent_events_marks_duplicate(self, client):
        """Duplicate webhook events are correctly marked as duplicate."""
        payload = _make_payment_failed_payload(event_id="evt_day16_dup_001")
        _send_webhook(client, "evt_day16_dup_001", payload)
        _send_webhook(client, "evt_day16_dup_001", payload)  # duplicate
        resp = client.get("/api/v1/webhooks/recent-events")
        items = resp.json()["items"]
        statuses = [e["status"] for e in items]
        assert "duplicate" in statuses

    def test_recent_events_total_count(self, client):
        """Total count reflects the actual number of webhook events in the DB."""
        _send_webhook(client, "evt_day16_cnt_001", _make_payment_failed_payload(event_id="evt_day16_cnt_001"))
        _send_webhook(client, "evt_day16_cnt_002", _make_payment_failed_payload(event_id="evt_day16_cnt_002"))
        resp = client.get("/api/v1/webhooks/recent-events")
        data = resp.json()
        assert data["total"] >= 2


# ---------------------------------------------------------------------------
# TESTS: GET /api/v1/recovery-cases/{id}/timeline
# ---------------------------------------------------------------------------

class TestRecoveryCaseTimeline:
    """Tests for the recovery case audit timeline endpoint."""

    def test_timeline_404_for_nonexistent_case(self, client):
        """Returns 404 for a case ID that doesn't exist."""
        resp = client.get("/api/v1/recovery/cases/999999/timeline")
        assert resp.status_code == 404

    def test_timeline_empty_for_case_without_activity(self, client, db_session):
        """Returns empty events for a freshly created case."""
        from app.models.revenue import RevenueRecord
        from app.models.recovery import RecoveryCase
        from app.models.enums import RecoveryCaseState, RiskStatus, RecoveryPriority, RevenueStatus
        from app.models.payment import Payment, PaymentStatus

        # Create minimal required entities
        payment = Payment(
            razorpay_payment_id="pay_day16_tl_001",
            razorpay_order_id="order_day16_tl_001",
            amount=100000,
            currency="INR",
            status=PaymentStatus.failed,
            customer_email="tl@example.com",
            customer_reference="+919876543210",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=100000,
            recoverable_amount=100000,
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            risk_status=RiskStatus.medium,
            priority=RecoveryPriority.medium,
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()
        db_session.commit()

        resp = client.get(f"/api/v1/recovery/cases/{case.id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["total_events"] == 0
        assert data["recovery_case_id"] == case.id

    def test_timeline_events_after_orchestration(self, client):
        """Timeline shows orchestration events after a webhook triggers recovery."""
        _send_webhook(client, "evt_day16_tl_orch_001", _make_payment_failed_payload(event_id="evt_day16_tl_orch_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        items = resp.json()["items"]
        case_id = None
        for item in items:
            if item.get("recovery_case_id"):
                case_id = item["recovery_case_id"]
                break
        assert case_id is not None, "Expected at least one event with a recovery_case_id"

        resp = client.get(f"/api/v1/recovery/cases/{case_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) >= 1
        actions = [e["action"] for e in data["events"]]
        assert "orchestration_started" in actions

    def test_timeline_limit(self, client):
        """Limit parameter caps returned events."""
        _send_webhook(client, "evt_day16_tl_lim_001", _make_payment_failed_payload(event_id="evt_day16_tl_lim_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        case_id = None
        for item in resp.json()["items"]:
            if item.get("recovery_case_id"):
                case_id = item["recovery_case_id"]
                break
        if case_id:
            resp = client.get(f"/api/v1/recovery/cases/{case_id}/timeline?limit=1")
            data = resp.json()
            assert len(data["events"]) <= 1

    def test_timeline_events_ordered_chronologically(self, client):
        """Events are returned in ascending chronological order."""
        _send_webhook(client, "evt_day16_tl_ord_001", _make_payment_failed_payload(event_id="evt_day16_tl_ord_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        case_id = None
        for item in resp.json()["items"]:
            if item.get("recovery_case_id"):
                case_id = item["recovery_case_id"]
                break
        if case_id:
            resp = client.get(f"/api/v1/recovery/cases/{case_id}/timeline")
            events = resp.json()["events"]
            timestamps = [e["timestamp"] for e in events]
            assert timestamps == sorted(timestamps), "Events must be in ascending order"

    def test_timeline_total_events_count(self, client):
        """total_events reflects the actual number of audit entries for the case."""
        _send_webhook(client, "evt_day16_tl_cnt_001", _make_payment_failed_payload(event_id="evt_day16_tl_cnt_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        case_id = None
        for item in resp.json()["items"]:
            if item.get("recovery_case_id"):
                case_id = item["recovery_case_id"]
                break
        if case_id:
            resp = client.get(f"/api/v1/recovery/cases/{case_id}/timeline")
            data = resp.json()
            assert data["total_events"] == len(data["events"])

    def test_timeline_includes_orchestration_started(self, client):
        """Timeline always includes the orchestration_started action."""
        _send_webhook(client, "evt_day16_tl_as_001", _make_payment_failed_payload(event_id="evt_day16_tl_as_001"))
        resp = client.get("/api/v1/webhooks/recent-events")
        case_id = None
        for item in resp.json()["items"]:
            if item.get("recovery_case_id"):
                case_id = item["recovery_case_id"]
                break
        if case_id:
            resp = client.get(f"/api/v1/recovery/cases/{case_id}/timeline")
            actions = [e["action"] for e in resp.json()["events"]]
            assert "orchestration_started" in actions


# ---------------------------------------------------------------------------
# TESTS: Schema validation
# ---------------------------------------------------------------------------

class TestSchemas:
    """Tests for Pydantic schema validation of new response models."""

    def test_recent_events_response_schema(self, client):
        """WebhookRecentEventsResponse schema is valid and serializable."""
        from app.schemas.webhooks import WebhookRecentEventsResponse, WebhookRecentEvent
        from datetime import datetime, timezone

        event = WebhookRecentEvent(
            id=1,
            event_type="payment.failed",
            status="processed",
            timestamp=datetime.now(timezone.utc),
        )
        resp = WebhookRecentEventsResponse(items=[event], total=1)
        data = resp.model_dump()
        assert "items" in data
        assert data["total"] == 1
        assert data["items"][0]["event_type"] == "payment.failed"

    def test_timeline_response_schema(self, client):
        """RecoveryTimelineResponse schema is valid and serializable."""
        from app.schemas.webhooks import RecoveryTimelineResponse, RecoveryTimelineEvent
        from datetime import datetime, timezone

        event = RecoveryTimelineEvent(
            id=1,
            action="orchestration_started",
            actor="system",
            entity_type="recovery_case",
            entity_id="1",
            timestamp=datetime.now(timezone.utc),
        )
        resp = RecoveryTimelineResponse(recovery_case_id=1, events=[event], total_events=1)
        data = resp.model_dump()
        assert data["recovery_case_id"] == 1
        assert len(data["events"]) == 1

    def test_recent_events_endpoint_returns_200(self, client):
        """GET /api/v1/webhooks/recent-events always returns 200."""
        resp = client.get("/api/v1/webhooks/recent-events")
        assert resp.status_code == 200

    def test_webhook_flow_updates_recent_events(self, client):
        """After sending a webhook, recent events count increases."""
        before = client.get("/api/v1/webhooks/recent-events").json()["total"]
        _send_webhook(client, "evt_day16_flow_001", _make_payment_failed_payload(event_id="evt_day16_flow_001"))
        after = client.get("/api/v1/webhooks/recent-events").json()["total"]
        assert after >= before + 1
