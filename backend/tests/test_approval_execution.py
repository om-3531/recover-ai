"""
Tests for Recovery Approval and Action Execution Workflow.

Covers:
- Approval creation, validation, and policy checks
- Rejection of terminal cases (recovered, closed) and zero balances
- Approval decision transitions (pending -> approved, pending -> rejected, expired)
- Execution authorization gates (rejecting pending/rejected/expired executions)
- Idempotent execution (no duplicate actions or execution side-effects)
- RecoveryCase state machine synchronization (open -> action_pending -> recovering)
- Retryable vs non-retryable execution failures
- REST API integration: /api/v1/approvals, /approve, /reject, /execute
- Comprehensive audit trail recording
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
from app.execution.mock_executor import MockRecoveryExecutor
from app.execution.service import RecoveryExecutionService
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
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord
from app.services.audit_service import AuditService


@pytest.fixture
def sample_case_for_approval(db_session):
    """Fixture creating a failed payment, at-risk revenue, and open recovery case."""
    payment = Payment(
        razorpay_payment_id="pay_appr_001",
        amount=500000,  # 5,000.00 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=500000,
        recoverable_amount=500000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="upi_payment_timeout",
        risk_status=RiskStatus.medium,
        priority=RecoveryPriority.medium,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    return case


# ---------------------------------------------------------------------------
# 1. APPROVAL CREATION & POLICY VALIDATION
# ---------------------------------------------------------------------------


def test_create_approval_request_success(db_session, sample_case_for_approval):
    """Test creating a valid approval request from a recommendation."""
    request = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.whatsapp,
        recommendation_id="rec_test_12345",
        requires_human_review=False,
    )

    approval = ApprovalService.create_approval(db_session, request)

    assert approval.id is not None
    assert approval.recovery_case_id == sample_case_for_approval.id
    assert approval.status == ApprovalStatus.pending
    assert approval.action_type == RecoveryActionType.payment_link
    assert approval.channel == RecoveryActionChannel.whatsapp
    assert approval.expires_at is not None
    expires_utc = approval.expires_at if approval.expires_at.tzinfo else approval.expires_at.replace(tzinfo=timezone.utc)
    assert expires_utc > datetime.now(timezone.utc)

    # Verify audit log
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_approval", entity_id=str(approval.id)
    )
    assert any(a.action == "approval_requested" for a in audits)



def test_create_approval_rejects_terminal_case(db_session, sample_case_for_approval):
    """Test creating an approval request for a recovered/closed case is blocked by policy."""
    sample_case_for_approval.current_state = RecoveryCaseState.recovered
    db_session.commit()

    request = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.email,
    )
    with pytest.raises(ApprovalPolicyBlockedError):
        ApprovalService.create_approval(db_session, request)


def test_create_approval_rejects_zero_recoverable_amount(db_session, sample_case_for_approval):
    """Test creating an approval request when recoverable amount is 0 is blocked."""
    sample_case_for_approval.revenue_record.recoverable_amount = 0
    db_session.commit()

    request = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.email,
    )
    with pytest.raises(ApprovalPolicyBlockedError):
        ApprovalService.create_approval(db_session, request)


def test_create_approval_case_not_found(db_session):
    """Test creating approval for non-existent case raises ApprovalNotFoundError."""
    request = ApprovalCreateRequest(
        recovery_case_id=99999,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.email,
    )
    with pytest.raises(ApprovalNotFoundError):
        ApprovalService.create_approval(db_session, request)


# ---------------------------------------------------------------------------
# 2. APPROVAL DECISION LIFECYCLE (APPROVE / REJECT / EXPIRE)
# ---------------------------------------------------------------------------


def test_approve_and_reject_approval_workflow(db_session, sample_case_for_approval):
    """Test approving and rejecting approval requests."""
    # 1. Create and Approve
    req = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    approval1 = ApprovalService.create_approval(db_session, req)

    approved = ApprovalService.approve_approval(
        db_session, approval1.id, ApprovalDecisionRequest(approved_by="supervisor_1")
    )
    assert approved.status == ApprovalStatus.approved
    assert approved.approved_by == "supervisor_1"
    assert approved.approved_at is not None

    # Cannot approve again
    with pytest.raises(ApprovalStateError):
        ApprovalService.approve_approval(db_session, approval1.id)

    # 2. Create and Reject
    approval2 = ApprovalService.create_approval(db_session, req)
    rejected = ApprovalService.reject_approval(
        db_session, approval2.id, ApprovalDecisionRequest(rejection_reason="Duplicate case")
    )
    assert rejected.status == ApprovalStatus.rejected
    assert rejected.rejection_reason == "Duplicate case"
    assert rejected.rejected_at is not None

    # Cannot approve a rejected approval
    with pytest.raises(ApprovalStateError):
        ApprovalService.approve_approval(db_session, approval2.id)


def test_expired_approval_handling(db_session, sample_case_for_approval):
    """Test that expired approval requests are rejected from decision and execution."""
    req = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.sms,
        expires_in_hours=1,
    )
    approval = ApprovalService.create_approval(db_session, req)

    # Artificially set expires_at in the past
    approval.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    with pytest.raises(ApprovalStateError):
        ApprovalService.approve_approval(db_session, approval.id)

    with pytest.raises(ExecutionAuthorizationError):
        RecoveryExecutionService.execute_approval(db_session, approval.id)


# ---------------------------------------------------------------------------
# 3. CONTROLLED EXECUTION & IDEMPOTENCY
# ---------------------------------------------------------------------------


def test_execute_approved_action_success_and_state_synchronization(
    db_session, sample_case_for_approval
):
    """
    Test executing an approved action:
    1. Calls executor
    2. Creates/updates RecoveryAction to executed
    3. Synchronizes RecoveryCase state machine to 'recovering'
    4. Records audit logs
    """
    req = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.whatsapp,
    )
    approval = ApprovalService.create_approval(db_session, req)
    ApprovalService.approve_approval(db_session, approval.id)

    # Execute
    exec_resp = RecoveryExecutionService.execute_approval(db_session, approval.id)

    assert exec_resp.approval_id == approval.id
    assert exec_resp.result.success is True
    assert exec_resp.result.status == RecoveryActionStatus.executed
    assert exec_resp.case_state == RecoveryCaseState.recovering

    # Verify RecoveryAction created in DB
    action = db_session.query(RecoveryAction).filter_by(id=exec_resp.recovery_action_id).first()
    assert action is not None
    assert action.status == RecoveryActionStatus.executed
    assert action.action_type == RecoveryActionType.payment_link
    assert action.channel == RecoveryActionChannel.whatsapp

    # Verify case state synchronized
    db_session.refresh(sample_case_for_approval)
    assert sample_case_for_approval.current_state == RecoveryCaseState.recovering

    # Verify audit logs
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_action", entity_id=str(action.id)
    )
    assert any(a.action == "execution_succeeded" for a in audits)


def test_execute_idempotency_returns_existing_result(db_session, sample_case_for_approval):
    """Test that executing an already executed approval is idempotent without duplicate actions."""
    req = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    approval = ApprovalService.create_approval(db_session, req)
    ApprovalService.approve_approval(db_session, approval.id)

    # First execution
    resp1 = RecoveryExecutionService.execute_approval(db_session, approval.id)
    action_count_before = db_session.query(RecoveryAction).filter_by(recovery_case_id=sample_case_for_approval.id).count()
    assert action_count_before == 1

    # Second execution (duplicate)
    resp2 = RecoveryExecutionService.execute_approval(db_session, approval.id)
    assert resp2.result.execution_id == resp1.result.execution_id
    assert resp2.recovery_action_id == resp1.recovery_action_id

    # Confirm no duplicate action created
    action_count_after = db_session.query(RecoveryAction).filter_by(recovery_case_id=sample_case_for_approval.id).count()
    assert action_count_after == 1


def test_cannot_execute_unapproved_or_rejected(db_session, sample_case_for_approval):
    """Test that pending and rejected approvals cannot be executed."""
    req = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.email,
    )
    # Pending execution attempt
    approval_pending = ApprovalService.create_approval(db_session, req)
    with pytest.raises(ExecutionAuthorizationError):
        RecoveryExecutionService.execute_approval(db_session, approval_pending.id)

    # Rejected execution attempt
    approval_rejected = ApprovalService.create_approval(db_session, req)
    ApprovalService.reject_approval(db_session, approval_rejected.id)
    with pytest.raises(ExecutionAuthorizationError):
        RecoveryExecutionService.execute_approval(db_session, approval_rejected.id)


def test_execution_failure_handling(db_session, sample_case_for_approval):
    """Test handling of executor failures and retryable flags."""
    req = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.sms_reminder,
        channel=RecoveryActionChannel.sms,
    )
    approval = ApprovalService.create_approval(db_session, req)
    ApprovalService.approve_approval(db_session, approval.id)

    # Execute with failing mock executor
    failing_executor = MockRecoveryExecutor(force_failure=True, retryable_failure=True)
    resp = RecoveryExecutionService.execute_approval(
        db_session, approval.id, executor=failing_executor
    )

    assert resp.result.success is False
    assert resp.result.status == RecoveryActionStatus.failed
    assert resp.result.retryable is True
    assert resp.result.error_code == "PROVIDER_ERROR"


# ---------------------------------------------------------------------------
# 4. REST API ENDPOINTS
# ---------------------------------------------------------------------------


def test_api_approval_and_execution_lifecycle(client, db_session, sample_case_for_approval):
    """Test complete approval and execution flow via REST API."""
    # 1. Create approval request
    create_resp = client.post(
        "/api/v1/approvals",
        json={
            "recovery_case_id": sample_case_for_approval.id,
            "action_type": "payment_link",
            "channel": "whatsapp",
            "recommendation_id": "rec_api_test_001",
        },
    )
    assert create_resp.status_code == 201
    approval_data = create_resp.json()
    approval_id = approval_data["id"]
    assert approval_data["status"] == "pending"

    # 2. List approvals with filters
    list_resp = client.get("/api/v1/approvals", params={"recovery_case_id": sample_case_for_approval.id, "status": "pending"})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 3. Get approval details
    get_resp = client.get(f"/api/v1/approvals/{approval_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == approval_id

    # 4. Reject endpoint test
    req2 = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    approval_to_reject = ApprovalService.create_approval(db_session, req2)
    reject_resp = client.post(
        f"/api/v1/approvals/{approval_to_reject.id}/reject",
        json={"approved_by": "supervisor_2", "rejection_reason": "Not appropriate channel"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    # 5. Approve original approval
    approve_resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"approved_by": "api_admin"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # 6. Execute (enforces server-side authority: no action_type/channel parameters accepted from client)
    exec_resp = client.post(f"/api/v1/approvals/{approval_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["result"]["success"] is True
    assert exec_data["case_state"] == "recovering"

    # 7. Repeat execution (idempotency check via API)
    exec_dup_resp = client.post(f"/api/v1/approvals/{approval_id}/execute")
    assert exec_dup_resp.status_code == 200
    assert exec_dup_resp.json()["result"]["execution_id"] == exec_data["result"]["execution_id"]


def test_non_retryable_execution_failure_handling(db_session, sample_case_for_approval):
    """Test handling of non-retryable executor failure."""
    req = ApprovalCreateRequest(
        recovery_case_id=sample_case_for_approval.id,
        action_type=RecoveryActionType.webhook_ping,
        channel=RecoveryActionChannel.webhook,
    )
    approval = ApprovalService.create_approval(db_session, req)
    ApprovalService.approve_approval(db_session, approval.id)

    perm_failing_executor = MockRecoveryExecutor(force_failure=True, retryable_failure=False)
    resp = RecoveryExecutionService.execute_approval(
        db_session, approval.id, executor=perm_failing_executor
    )

    assert resp.result.success is False
    assert resp.result.status == RecoveryActionStatus.failed
    assert resp.result.retryable is False
    assert resp.result.error_code == "PERMANENT_ERROR"

