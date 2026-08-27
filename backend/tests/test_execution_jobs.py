"""
Tests for Recovery Execution Jobs and Multi-Channel Communication Providers.

Covers:
1. Job creation & lifecycle states
2. Server-side approval status prerequisite enforcement
3. Rejection of pending, rejected, and expired approvals
4. Protection against terminal recovery cases
5. Successful mock dispatch across Email, SMS, WhatsApp, and Webhook channels
6. Retryable provider failures and exponential retry backoff scheduling
7. Permanent provider failure handling
8. Max retry attempt boundary guard
9. Strict database-level and service-level idempotency
10. Duplicate worker execution protection
11. In-memory queue and JobWorker drainage
12. Real provider safe unconfigured behavior (zero network calls)
13. Comprehensive audit logging for all job milestones
14. REST API job inquiry routes
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.core.exceptions import NotFoundError
from app.execution.exceptions import ExecutionAuthorizationError
from app.jobs.exceptions import JobNotFoundError
from app.jobs.queue import InMemoryJobQueue
from app.jobs.schemas import JobCreateRequest
from app.jobs.service import JobService
from app.jobs.worker import JobWorker
from app.models.approval import RecoveryApproval
from app.models.enums import (
    ApprovalStatus,
    JobStatus,
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
from app.models.job import RecoveryExecutionJob
from app.models.payment import Payment
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord
from app.providers.email import MockEmailProvider, SendGridEmailProvider
from app.providers.registry import ProviderRegistry
from app.providers.sms import MockSMSProvider, TwilioSMSProvider
from app.providers.webhook import MockWebhookProvider
from app.providers.whatsapp import MetaWhatsAppProvider, MockWhatsAppProvider
from app.services.audit_service import AuditService


@pytest.fixture
def sample_approved_job_fixture(db_session):
    """Fixture creating payment, revenue, case, and approved recovery approval."""
    payment = Payment(
        razorpay_payment_id="pay_job_001",
        amount=250000,  # 2,500.00 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
        customer_email="customer@example.com",
        customer_reference="+919876543210",
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=250000,
        recoverable_amount=250000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="insufficient_funds",
        risk_status=RiskStatus.low,
        priority=RecoveryPriority.high,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.flush()

    approval = RecoveryApproval(
        recovery_case_id=case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
        status=ApprovalStatus.approved,
        requires_human_review=False,
        approved_by="supervisor_user",
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add(approval)
    db_session.commit()
    db_session.refresh(approval)

    return approval


# ---------------------------------------------------------------------------
# 1. JOB CREATION & PREREQUISITES
# ---------------------------------------------------------------------------


def test_job_creation_and_queued_state(db_session, sample_approved_job_fixture):
    """Test creating an execution job in queued status without immediate processing."""
    approval = sample_approved_job_fixture
    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=False,
    )

    assert job.id is not None
    assert job.status == JobStatus.queued
    assert job.attempt_count == 0
    assert job.max_attempts == 3
    assert job.recovery_case_id == approval.recovery_case_id
    assert job.recovery_approval_id == approval.id
    assert "approval:" in job.idempotency_key

    # Audit log
    audits, _ = AuditService.list_audit_logs(
        db_session, entity_type="recovery_execution_job", entity_id=str(job.id)
    )
    actions = [a.action for a in audits]
    assert "execution_queued" in actions


def test_job_rejects_pending_approval(db_session, sample_approved_job_fixture):
    """Test that jobs cannot be created for pending approvals."""
    approval = sample_approved_job_fixture
    approval.status = ApprovalStatus.pending
    db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc:
        JobService.create_job(db=db_session, approval_id=approval.id)
    assert "pending" in str(exc.value).lower()


def test_job_rejects_rejected_approval(db_session, sample_approved_job_fixture):
    """Test that jobs cannot be created for rejected approvals."""
    approval = sample_approved_job_fixture
    approval.status = ApprovalStatus.rejected
    db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc:
        JobService.create_job(db=db_session, approval_id=approval.id)
    assert "rejected" in str(exc.value).lower()


def test_job_rejects_expired_approval(db_session, sample_approved_job_fixture):
    """Test that expired approvals are rejected and their status updated."""
    approval = sample_approved_job_fixture
    approval.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc:
        JobService.create_job(db=db_session, approval_id=approval.id)
    assert "expired" in str(exc.value).lower()

    db_session.refresh(approval)
    assert approval.status == ApprovalStatus.expired


def test_job_rejects_terminal_recovery_case(db_session, sample_approved_job_fixture):
    """Test that execution jobs are blocked for cases in terminal state."""
    approval = sample_approved_job_fixture
    approval.recovery_case.current_state = RecoveryCaseState.recovered
    db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc:
        JobService.create_job(db=db_session, approval_id=approval.id)
    assert "terminal state" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 2. SUCCESSFUL MULTI-CHANNEL DISPATCH
# ---------------------------------------------------------------------------


def test_successful_mock_email_dispatch(db_session, sample_approved_job_fixture):
    """Test successful dispatch and state synchronization for email channel."""
    approval = sample_approved_job_fixture
    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
    )

    assert job.status == JobStatus.succeeded
    assert job.attempt_count == 1
    assert job.completed_at is not None
    assert job.result is not None
    assert job.result["success"] is True
    assert "msg_email_" in job.result["provider_message_id"]

    # Verify RecoveryAction created & state machine synced
    db_session.refresh(approval)
    assert approval.recovery_action_id is not None
    action = approval.recovery_action
    assert action.status == RecoveryActionStatus.executed
    assert action.result["success"] is True

    case = approval.recovery_case
    assert case.current_state == RecoveryCaseState.recovering

    # Verify audit logs
    audits, _ = AuditService.list_audit_logs(
        db_session, entity_type="recovery_execution_job", entity_id=str(job.id)
    )
    actions = [a.action for a in audits]
    assert "execution_queued" in actions
    assert "execution_started" in actions
    assert "provider_dispatch_started" in actions
    assert "provider_dispatch_succeeded" in actions
    assert "execution_succeeded" in actions


def test_successful_mock_sms_dispatch(db_session, sample_approved_job_fixture):
    """Test successful dispatch for SMS channel."""
    approval = sample_approved_job_fixture
    approval.action_type = RecoveryActionType.sms_reminder
    approval.channel = RecoveryActionChannel.sms
    db_session.commit()

    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
    )

    assert job.status == JobStatus.succeeded
    assert "msg_sms_" in job.result["provider_message_id"]


def test_successful_mock_whatsapp_dispatch(db_session, sample_approved_job_fixture):
    """Test successful dispatch for WhatsApp channel."""
    approval = sample_approved_job_fixture
    approval.action_type = RecoveryActionType.whatsapp_reminder
    approval.channel = RecoveryActionChannel.whatsapp
    db_session.commit()

    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
    )

    assert job.status == JobStatus.succeeded
    assert "msg_wa_" in job.result["provider_message_id"]


def test_successful_mock_webhook_dispatch(db_session, sample_approved_job_fixture):
    """Test successful dispatch for Webhook channel."""
    approval = sample_approved_job_fixture
    approval.action_type = RecoveryActionType.webhook_ping
    approval.channel = RecoveryActionChannel.webhook
    db_session.commit()

    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
    )

    assert job.status == JobStatus.succeeded
    assert "msg_hook_" in job.result["provider_message_id"]


# ---------------------------------------------------------------------------
# 3. RETRY & FAILURE BEHAVIOR
# ---------------------------------------------------------------------------


def test_retryable_provider_failure_schedules_retry(
    db_session, sample_approved_job_fixture
):
    """Test that retryable provider failures schedule a retry and calculate next_retry_at."""
    approval = sample_approved_job_fixture
    failing_reg = ProviderRegistry()
    failing_reg.register(
        RecoveryActionChannel.email,
        MockEmailProvider(force_failure=True, retryable_failure=True),
    )

    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
        registry=failing_reg,
    )

    assert job.status == JobStatus.retry_scheduled
    assert job.attempt_count == 1
    assert job.next_retry_at is not None
    assert job.error_code == "EMAIL_GATEWAY_TIMEOUT"
    assert job.result["retryable"] is True

    # Case must NOT be marked recovered
    case = approval.recovery_case
    assert case.current_state != RecoveryCaseState.recovered

    # Verify audit logs
    audits, _ = AuditService.list_audit_logs(
        db_session, entity_type="recovery_execution_job", entity_id=str(job.id)
    )
    actions = [a.action for a in audits]
    assert "execution_retry_scheduled" in actions


def test_permanent_provider_failure_marks_job_failed(
    db_session, sample_approved_job_fixture
):
    """Test that permanent non-retryable failures immediately mark job as failed."""
    approval = sample_approved_job_fixture
    failing_reg = ProviderRegistry()
    failing_reg.register(
        RecoveryActionChannel.email,
        MockEmailProvider(force_failure=True, retryable_failure=False),
    )

    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
        registry=failing_reg,
    )

    assert job.status == JobStatus.failed
    assert job.attempt_count == 1
    assert job.completed_at is not None
    assert job.error_code == "INVALID_EMAIL_ADDRESS"
    assert job.result["retryable"] is False

    # Action marked failed
    db_session.refresh(approval)
    assert approval.recovery_action.status == RecoveryActionStatus.failed


def test_max_retry_attempt_boundary_guard(
    db_session, sample_approved_job_fixture
):
    """Test that retryable failures transition to failed once max_attempts is reached."""
    approval = sample_approved_job_fixture
    failing_reg = ProviderRegistry()
    failing_reg.register(
        RecoveryActionChannel.email,
        MockEmailProvider(force_failure=True, retryable_failure=True),
    )

    # Attempt 1
    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        max_attempts=3,
        auto_process=True,
        registry=failing_reg,
    )
    assert job.status == JobStatus.retry_scheduled
    assert job.attempt_count == 1

    # Attempt 2
    job = JobService.process_job(db=db_session, job_id=job.id, registry=failing_reg)
    assert job.status == JobStatus.retry_scheduled
    assert job.attempt_count == 2

    # Attempt 3 (Final attempt -> should fail)
    job = JobService.process_job(db=db_session, job_id=job.id, registry=failing_reg)
    assert job.status == JobStatus.failed
    assert job.attempt_count == 3
    assert job.completed_at is not None


# ---------------------------------------------------------------------------
# 4. IDEMPOTENCY & WORKER EXECUTION
# ---------------------------------------------------------------------------


def test_idempotent_job_creation_returns_existing(
    db_session, sample_approved_job_fixture
):
    """Test that duplicate create_job calls return the existing job record."""
    approval = sample_approved_job_fixture

    job1 = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=False,
    )

    job2 = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=False,
    )

    assert job1.id == job2.id
    assert job1.idempotency_key == job2.idempotency_key

    # Total jobs in database is exactly 1
    total_jobs = db_session.query(RecoveryExecutionJob).count()
    assert total_jobs == 1


def test_duplicate_worker_execution_safety(
    db_session, sample_approved_job_fixture
):
    """Test that processing an already succeeded job returns cached result without re-executing."""
    approval = sample_approved_job_fixture
    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
    )
    assert job.status == JobStatus.succeeded
    assert job.attempt_count == 1

    # Re-process
    job_reprocessed = JobService.process_job(db=db_session, job_id=job.id)
    assert job_reprocessed.status == JobStatus.succeeded
    assert job_reprocessed.attempt_count == 1  # Not incremented


def test_in_memory_queue_and_job_worker(db_session, sample_approved_job_fixture):
    """Test enqueuing and processing jobs via JobWorker."""
    approval = sample_approved_job_fixture
    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=False,
    )

    queue = InMemoryJobQueue()
    queue.enqueue(job.id)
    assert queue.size() == 1

    processed_count = JobWorker.drain_queue(db=db_session, queue=queue)
    assert processed_count == 1
    assert queue.size() == 0

    db_session.refresh(job)
    assert job.status == JobStatus.succeeded


# ---------------------------------------------------------------------------
# 5. REAL PROVIDER SAFETIES & API ROUTES
# ---------------------------------------------------------------------------


def test_real_providers_unconfigured_safe_handling():
    """Test that real provider foundations return clear errors when unconfigured without network calls."""
    from app.providers.base import ProviderContext

    ctx = ProviderContext(
        recovery_case_id=1,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
        customer_email="test@example.com",
    )

    sg = SendGridEmailProvider(api_key="")
    res = sg.send(ctx)
    assert res.success is False
    assert res.error_code == "PROVIDER_NOT_CONFIGURED"

    tw = TwilioSMSProvider(account_sid="", auth_token="", from_number="")
    res_tw = tw.send(ctx)
    assert res_tw.success is False
    assert res_tw.error_code == "PROVIDER_NOT_CONFIGURED"

    wa = MetaWhatsAppProvider(access_token="", phone_number_id="")
    res_wa = wa.send(ctx)
    assert res_wa.success is False
    assert res_wa.error_code == "PROVIDER_NOT_CONFIGURED"


def test_api_execution_jobs_endpoints(client, db_session, sample_approved_job_fixture):
    """Test REST API endpoints for execution jobs."""
    approval = sample_approved_job_fixture
    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=True,
    )

    # 1. GET /api/v1/execution-jobs/{job_id}
    res = client.get(f"/api/v1/execution-jobs/{job.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == job.id
    assert data["status"] == "succeeded"
    assert data["recovery_case_id"] == approval.recovery_case_id

    # 2. GET /api/v1/recovery-cases/{case_id}/execution-jobs
    res_case = client.get(
        f"/api/v1/recovery-cases/{approval.recovery_case_id}/execution-jobs"
    )
    assert res_case.status_code == 200
    case_jobs = res_case.json()
    assert case_jobs["total"] == 1
    assert case_jobs["items"][0]["id"] == job.id

    # 3. GET /api/v1/execution-jobs (list all with filters)
    res_list = client.get("/api/v1/execution-jobs?status=succeeded")
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1


def test_job_service_list_with_approval_and_case_filters(
    db_session, sample_approved_job_fixture
):
    """Test JobService list_jobs with approval_id and case_id filters."""
    approval = sample_approved_job_fixture
    job = JobService.create_job(
        db=db_session,
        approval_id=approval.id,
        auto_process=False,
    )

    # Filter by approval_id
    jobs_appr, total_appr = JobService.list_jobs(
        db=db_session, approval_id=approval.id
    )
    assert total_appr >= 1
    assert any(j.id == job.id for j in jobs_appr)

    # Filter by non-existent approval
    jobs_none, total_none = JobService.list_jobs(
        db=db_session, approval_id=99999
    )
    assert total_none == 0
    assert len(jobs_none) == 0

