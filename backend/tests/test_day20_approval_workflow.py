"""
Tests for Day 20 — Interactive Approval Workflow.

Covers:
- Approval listing with status/case filters via REST API
- Approve and reject decision lifecycle via REST API
- Approval trigger → execution lifecycle (approve then execute)
- Approval expiration handling
- Audit trail verification for approval decisions
- Concurrent approve/reject race condition safety
- Approval policy validation (terminal states, zero balance)
- List pending approvals endpoint
- Full buildathon demo flow (high-risk → approve → execute → verify)
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.approval.exceptions import (
    ApprovalNotFoundError,
    ApprovalPolicyBlockedError,
    ApprovalStateError,
)
from app.approval.schemas import ApprovalCreateRequest, ApprovalDecisionRequest
from app.approval.service import ApprovalService
from app.execution.exceptions import ExecutionAuthorizationError
from app.models.enums import (
    ApprovalStatus,
    PaymentMethod,
    PaymentStatus,
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueStatus,
    RiskStatus,
)
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.services.audit_service import AuditService


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def high_risk_case(db_session):
    """Fixture creating a high-risk open recovery case for approval testing."""
    payment = Payment(
        razorpay_payment_id="pay_day20_001",
        amount=1500000,  # 15,000 INR — high value
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=1500000,
        recoverable_amount=1500000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="upi_payment_failure_high_value",
        risk_status=RiskStatus.high,
        priority=RecoveryPriority.high,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def low_risk_case(db_session):
    """Fixture creating a low-risk open recovery case for approval testing."""
    payment = Payment(
        razorpay_payment_id="pay_day20_002",
        amount=25000,  # 250 INR — low value
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=25000,
        recoverable_amount=25000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="upi_payment_failure_low_value",
        risk_status=RiskStatus.low,
        priority=RecoveryPriority.low,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def pending_approval_for_high_risk(db_session, high_risk_case):
    """Fixture creating a pending approval request on the high-risk case."""
    req = ApprovalCreateRequest(
        recovery_case_id=high_risk_case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
        recommendation_id="rec_day20_high_risk",
        requires_human_review=True,
    )
    return ApprovalService.create_approval(db_session, req)


@pytest.fixture
def pending_approval_for_low_risk(db_session, low_risk_case):
    """Fixture creating a pending approval request on the low-risk case."""
    req = ApprovalCreateRequest(
        recovery_case_id=low_risk_case.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.whatsapp,
        recommendation_id="rec_day20_low_risk",
        requires_human_review=False,
    )
    return ApprovalService.create_approval(db_session, req)


# ---------------------------------------------------------------------------
# 1. APPROVAL LISTING & FILTERING (REST API)
# ---------------------------------------------------------------------------


def test_list_approvals_returns_all(client, db_session, high_risk_case, low_risk_case):
    """Test listing all approvals returns both pending approvals."""
    req1 = ApprovalCreateRequest(
        recovery_case_id=high_risk_case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    req2 = ApprovalCreateRequest(
        recovery_case_id=low_risk_case.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.whatsapp,
    )
    ApprovalService.create_approval(db_session, req1)
    ApprovalService.create_approval(db_session, req2)

    resp = client.get("/api/v1/approvals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


def test_list_approvals_filter_by_status(client, db_session, pending_approval_for_high_risk):
    """Test filtering approvals by status=pending."""
    resp = client.get("/api/v1/approvals", params={"status": "pending"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(item["status"] == "pending" for item in data["items"])


def test_list_approvals_filter_by_case(client, db_session, high_risk_case, pending_approval_for_high_risk):
    """Test filtering approvals by recovery_case_id."""
    resp = client.get(
        "/api/v1/approvals",
        params={"recovery_case_id": high_risk_case.id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(
        item["recovery_case_id"] == high_risk_case.id for item in data["items"]
    )


def test_list_approvals_filter_by_status_and_case(
    client, db_session, high_risk_case, pending_approval_for_high_risk
):
    """Test combined status and case_id filter."""
    resp = client.get(
        "/api/v1/approvals",
        params={"status": "pending", "recovery_case_id": high_risk_case.id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_list_approvals_empty_result(client):
    """Test listing approvals with no matching filter returns empty list."""
    resp = client.get("/api/v1/approvals", params={"status": "rejected"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


def test_get_approval_by_id(client, db_session, pending_approval_for_high_risk):
    """Test fetching a single approval by ID."""
    approval_id = pending_approval_for_high_risk.id
    resp = client.get(f"/api/v1/approvals/{approval_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == approval_id
    assert data["status"] == "pending"
    assert data["requires_human_review"] is True


def test_get_approval_not_found(client):
    """Test fetching non-existent approval returns 404."""
    resp = client.get("/api/v1/approvals/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. APPROVE DECISION LIFECYCLE (REST API)
# ---------------------------------------------------------------------------


def test_approve_pending_approval(client, db_session, pending_approval_for_high_risk):
    """Test approving a pending approval via REST API."""
    approval_id = pending_approval_for_high_risk.id
    resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"approved_by": "demo_judge"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == "demo_judge"
    assert data["approved_at"] is not None


def test_approve_sets_correct_approver(client, db_session, pending_approval_for_high_risk):
    """Test that the approve endpoint records the approver identity."""
    approval_id = pending_approval_for_high_risk.id
    resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"approved_by": "supervisor_alpha"},
    )
    assert resp.status_code == 200
    assert resp.json()["approved_by"] == "supervisor_alpha"


def test_approve_already_approved_fails(client, db_session, pending_approval_for_high_risk):
    """Test that approving an already-approved approval raises error."""
    approval_id = pending_approval_for_high_risk.id
    # First approve
    client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approved_by": "j1"})
    # Second approve should fail
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approved_by": "j2"})
    assert resp.status_code == 400 or resp.status_code == 409


def test_approve_not_found(client):
    """Test approving non-existent approval returns 404."""
    resp = client.post("/api/v1/approvals/99999/approve", json={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. REJECT DECISION LIFECYCLE (REST API)
# ---------------------------------------------------------------------------


def test_reject_pending_approval(client, db_session, pending_approval_for_high_risk):
    """Test rejecting a pending approval via REST API."""
    approval_id = pending_approval_for_high_risk.id
    resp = client.post(
        f"/api/v1/approvals/{approval_id}/reject",
        json={
            "approved_by": "demo_judge",
            "rejection_reason": "Customer has already been contacted",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Customer has already been contacted"
    assert data["rejected_at"] is not None


def test_reject_without_reason_uses_default(client, db_session, pending_approval_for_low_risk):
    """Test rejecting without providing a reason uses default."""
    approval_id = pending_approval_for_low_risk.id
    resp = client.post(f"/api/v1/approvals/{approval_id}/reject", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] is not None


def test_reject_already_rejected_fails(client, db_session, pending_approval_for_high_risk):
    """Test that rejecting an already-rejected approval raises error."""
    approval_id = pending_approval_for_high_risk.id
    client.post(f"/api/v1/approvals/{approval_id}/reject", json={"rejection_reason": "First"})
    resp = client.post(f"/api/v1/approvals/{approval_id}/reject", json={"rejection_reason": "Second"})
    assert resp.status_code == 400 or resp.status_code == 409


def test_cannot_approve_rejected_approval(client, db_session, pending_approval_for_high_risk):
    """Test that approving a rejected approval raises error."""
    approval_id = pending_approval_for_high_risk.id
    client.post(f"/api/v1/approvals/{approval_id}/reject", json={"rejection_reason": "no"})
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approved_by": "j1"})
    assert resp.status_code == 400 or resp.status_code == 409


# ---------------------------------------------------------------------------
# 4. APPROVE → EXECUTE LIFECYCLE (END-TO-END)
# ---------------------------------------------------------------------------


def test_approve_then_execute_full_lifecycle(
    client, db_session, pending_approval_for_high_risk
):
    """Test the full buildathon demo flow: approve then execute."""
    approval_id = pending_approval_for_high_risk.id

    # Step 1: Approve
    approve_resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"approved_by": "demo_judge"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # Step 2: Execute
    exec_resp = client.post(f"/api/v1/approvals/{approval_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["result"]["success"] is True
    assert exec_data["result"]["status"] == "executed"
    assert exec_data["case_state"] == "recovering"

    # Step 3: Verify case state
    case = db_session.query(RecoveryCase).filter_by(
        id=pending_approval_for_high_risk.recovery_case_id
    ).first()
    assert case.current_state == RecoveryCaseState.recovering


def test_cannot_execute_pending_approval(client, db_session, pending_approval_for_high_risk):
    """Test that executing a pending (unapproved) approval is rejected."""
    approval_id = pending_approval_for_high_risk.id
    resp = client.post(f"/api/v1/approvals/{approval_id}/execute")
    assert resp.status_code == 400 or resp.status_code == 403


def test_cannot_execute_rejected_approval(client, db_session, pending_approval_for_high_risk):
    """Test that executing a rejected approval is rejected."""
    approval_id = pending_approval_for_high_risk.id
    client.post(f"/api/v1/approvals/{approval_id}/reject", json={"rejection_reason": "no"})
    resp = client.post(f"/api/v1/approvals/{approval_id}/execute")
    assert resp.status_code == 400 or resp.status_code == 403


def test_execute_idempotency_after_approve(
    client, db_session, pending_approval_for_high_risk
):
    """Test that executing an already-executed approval returns the same result (idempotent)."""
    approval_id = pending_approval_for_high_risk.id
    client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approved_by": "j1"})

    resp1 = client.post(f"/api/v1/approvals/{approval_id}/execute")
    resp2 = client.post(f"/api/v1/approvals/{approval_id}/execute")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["result"]["execution_id"] == resp2.json()["result"]["execution_id"]


# ---------------------------------------------------------------------------
# 5. AUDIT TRAIL VERIFICATION
# ---------------------------------------------------------------------------


def test_approve_records_audit_log(db_session, pending_approval_for_high_risk):
    """Test that approving an approval creates an audit log entry."""
    approval_id = pending_approval_for_high_risk.id
    ApprovalService.approve_approval(
        db_session,
        approval_id,
        ApprovalDecisionRequest(approved_by="audit_test_judge"),
    )

    audits, total = AuditService.list_audit_logs(
        db_session,
        entity_type="recovery_approval",
        entity_id=str(approval_id),
    )
    assert any(a.action == "approval_approved" for a in audits)
    assert any(a.actor == "audit_test_judge" for a in audits)


def test_reject_records_audit_log(db_session, pending_approval_for_high_risk):
    """Test that rejecting an approval creates an audit log entry."""
    approval_id = pending_approval_for_high_risk.id
    ApprovalService.reject_approval(
        db_session,
        approval_id,
        ApprovalDecisionRequest(
            approved_by="audit_rejector",
            rejection_reason="Audit test rejection",
        ),
    )

    audits, total = AuditService.list_audit_logs(
        db_session,
        entity_type="recovery_approval",
        entity_id=str(approval_id),
    )
    assert any(a.action == "approval_rejected" for a in audits)
    assert any(a.actor == "audit_rejector" for a in audits)


# ---------------------------------------------------------------------------
# 6. CONCURRENT / RACE CONDITION SAFETY
# ---------------------------------------------------------------------------


def test_concurrent_approve_reject_second_fails(db_session, high_risk_case):
    """Test that if two operators race to decide, only one succeeds."""
    req = ApprovalCreateRequest(
        recovery_case_id=high_risk_case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    approval = ApprovalService.create_approval(db_session, req)

    # First operator approves
    ApprovalService.approve_approval(
        db_session, approval.id, ApprovalDecisionRequest(approved_by="op1")
    )

    # Second operator tries to reject — should fail
    with pytest.raises(ApprovalStateError):
        ApprovalService.reject_approval(
            db_session, approval.id, ApprovalDecisionRequest(approved_by="op2")
        )


# ---------------------------------------------------------------------------
# 7. POLICY VALIDATION EDGE CASES
# ---------------------------------------------------------------------------


def test_cannot_create_approval_for_recovered_case(db_session):
    """Test that creating an approval for a recovered case is blocked."""
    payment = Payment(
        razorpay_payment_id="pay_policy_001",
        amount=100000,
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()
    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=100000,
        recoverable_amount=100000,
        currency="INR",
        status=RevenueStatus.recovered,
    )
    db_session.add(revenue)
    db_session.flush()
    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="test",
        risk_status=RiskStatus.low,
        priority=RecoveryPriority.low,
        current_state=RecoveryCaseState.recovered,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    req = ApprovalCreateRequest(
        recovery_case_id=case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    with pytest.raises(ApprovalPolicyBlockedError):
        ApprovalService.create_approval(db_session, req)


def test_cannot_create_approval_for_closed_case(db_session):
    """Test that creating an approval for a closed case is blocked."""
    payment = Payment(
        razorpay_payment_id="pay_policy_002",
        amount=100000,
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()
    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=100000,
        recoverable_amount=100000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()
    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="test",
        risk_status=RiskStatus.low,
        priority=RecoveryPriority.low,
        current_state=RecoveryCaseState.closed,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    req = ApprovalCreateRequest(
        recovery_case_id=case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    with pytest.raises(ApprovalPolicyBlockedError):
        ApprovalService.create_approval(db_session, req)


def test_cannot_create_approval_for_zero_balance(db_session):
    """Test that creating an approval for zero recoverable amount is blocked."""
    payment = Payment(
        razorpay_payment_id="pay_policy_003",
        amount=100000,
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()
    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=100000,
        recoverable_amount=0,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()
    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="test",
        risk_status=RiskStatus.low,
        priority=RecoveryPriority.low,
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
    with pytest.raises(ApprovalPolicyBlockedError):
        ApprovalService.create_approval(db_session, req)


# ---------------------------------------------------------------------------
# 8. EXPIRATION HANDLING
# ---------------------------------------------------------------------------


def test_expired_approval_cannot_be_approved(db_session, high_risk_case):
    """Test that an expired approval cannot be approved."""
    req = ApprovalCreateRequest(
        recovery_case_id=high_risk_case.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.sms,
        expires_in_hours=1,
    )
    approval = ApprovalService.create_approval(db_session, req)
    # Artificially expire it
    approval.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    with pytest.raises(ApprovalStateError):
        ApprovalService.approve_approval(db_session, approval.id)


def test_expired_approval_cannot_be_rejected(db_session, high_risk_case):
    """Test that an expired approval cannot be rejected."""
    req = ApprovalCreateRequest(
        recovery_case_id=high_risk_case.id,
        action_type=RecoveryActionType.sms_reminder,
        channel=RecoveryActionChannel.sms,
        expires_in_hours=1,
    )
    approval = ApprovalService.create_approval(db_session, req)
    approval.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    with pytest.raises(ApprovalStateError):
        ApprovalService.reject_approval(db_session, approval.id)


# ---------------------------------------------------------------------------
# 9. RESPONSE SCHEMA VALIDATION
# ---------------------------------------------------------------------------


def test_approval_response_contains_all_fields(
    client, db_session, pending_approval_for_high_risk
):
    """Test that the approval response contains all expected fields."""
    resp = client.get(f"/api/v1/approvals/{pending_approval_for_high_risk.id}")
    data = resp.json()
    required_fields = [
        "id", "recovery_case_id", "action_type", "channel", "status",
        "requires_human_review", "requested_at", "created_at", "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


def test_approval_list_response_pagination(client, db_session, high_risk_case):
    """Test that approval list pagination works correctly."""
    # Create 3 approvals
    for i in range(3):
        req = ApprovalCreateRequest(
            recovery_case_id=high_risk_case.id,
            action_type=RecoveryActionType.email_reminder,
            channel=RecoveryActionChannel.email,
        )
        ApprovalService.create_approval(db_session, req)

    # Fetch with limit=2
    resp = client.get("/api/v1/approvals", params={"limit": 2})
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["total"] >= 3
