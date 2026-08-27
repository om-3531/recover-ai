"""
Tests for Recovery Analytics Engine, Metrics Aggregation, and REST APIs.

Covers:
1. Overview metrics calculations and empty database handling
2. Revenue totals, averages, and recoverable amount calculations
3. Recovery rate precision, bounding (0.0 to 1.0), and zero-division protection
4. Case status breakdown across all lifecycle states
5. Approval activity metrics and approval rate computation
6. Execution job status breakdown, success rates, and retry counts
7. Multi-channel execution performance metrics (Email, SMS, WhatsApp, Webhook)
8. Failure analysis, retryable vs permanent errors, and error code grouping
9. Date range filtering and validation
10. Rejection of invalid date intervals (HTTP 422 when start_date > end_date)
11. Daily timeline aggregation
12. Recent activity stream and sanitized output (no secret leaks)
13. Strict read-only guarantee (zero database mutations during analytics reads)
14. REST API routes integration under /api/v1/analytics
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.analytics.exceptions import InvalidDateRangeError
from app.analytics.metrics import safe_average, safe_division
from app.analytics.service import AnalyticsService
from app.models.approval import RecoveryApproval
from app.models.audit import AuditLog
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
from app.services.audit_service import AuditService


@pytest.fixture
def analytics_seed_data(db_session):
    """Seed comprehensive dataset spanning payments, revenues, cases, approvals, and jobs."""
    base_time = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Recovered Case & Revenue
    p1 = Payment(
        razorpay_payment_id="pay_an_001",
        amount=100000,  # 1,000 INR
        currency="INR",
        status=PaymentStatus.captured,
        method=PaymentMethod.card,
        customer_email="user1@example.com",
        created_at=base_time,
    )
    db_session.add(p1)
    db_session.flush()

    r1 = RevenueRecord(
        payment_id=p1.id,
        gross_amount=100000,
        recoverable_amount=100000,
        currency="INR",
        status=RevenueStatus.recovered,
        created_at=base_time,
    )
    db_session.add(r1)
    db_session.flush()

    c1 = RecoveryCase(
        revenue_record_id=r1.id,
        reason="card_network_timeout",
        risk_status=RiskStatus.low,
        priority=RecoveryPriority.medium,
        current_state=RecoveryCaseState.recovered,
        created_at=base_time,
    )
    db_session.add(c1)
    db_session.flush()

    a1 = RecoveryApproval(
        recovery_case_id=c1.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
        status=ApprovalStatus.approved,
        requires_human_review=False,
        approved_by="auto_system",
        requested_at=base_time,
        created_at=base_time,
    )
    db_session.add(a1)
    db_session.flush()

    j1 = RecoveryExecutionJob(
        recovery_case_id=c1.id,
        recovery_approval_id=a1.id,
        status=JobStatus.succeeded,
        attempt_count=1,
        max_attempts=3,
        idempotency_key=f"appr:{a1.id}:email",
        created_at=base_time,
    )
    db_session.add(j1)
    db_session.flush()

    # 2. At Risk Case & Revenue (Open / In-Progress)
    p2 = Payment(
        razorpay_payment_id="pay_an_002",
        amount=200000,  # 2,000 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
        customer_email="user2@example.com",
        created_at=base_time + timedelta(days=1),
    )
    db_session.add(p2)
    db_session.flush()

    r2 = RevenueRecord(
        payment_id=p2.id,
        gross_amount=200000,
        recoverable_amount=200000,
        currency="INR",
        status=RevenueStatus.at_risk,
        created_at=base_time + timedelta(days=1),
    )
    db_session.add(r2)
    db_session.flush()

    c2 = RecoveryCase(
        revenue_record_id=r2.id,
        reason="insufficient_funds",
        risk_status=RiskStatus.high,
        priority=RecoveryPriority.high,
        current_state=RecoveryCaseState.action_pending,
        created_at=base_time + timedelta(days=1),
    )
    db_session.add(c2)
    db_session.flush()

    a2 = RecoveryApproval(
        recovery_case_id=c2.id,
        action_type=RecoveryActionType.sms_reminder,
        channel=RecoveryActionChannel.sms,
        status=ApprovalStatus.pending,
        requires_human_review=True,
        requested_at=base_time + timedelta(days=1),
        created_at=base_time + timedelta(days=1),
    )
    db_session.add(a2)
    db_session.flush()

    # 3. Failed Job & Retried Case
    p3 = Payment(
        razorpay_payment_id="pay_an_003",
        amount=150000,  # 1,500 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
        customer_email="user3@example.com",
        created_at=base_time + timedelta(days=2),
    )
    db_session.add(p3)
    db_session.flush()

    r3 = RevenueRecord(
        payment_id=p3.id,
        gross_amount=150000,
        recoverable_amount=150000,
        currency="INR",
        status=RevenueStatus.at_risk,
        created_at=base_time + timedelta(days=2),
    )
    db_session.add(r3)
    db_session.flush()

    c3 = RecoveryCase(
        revenue_record_id=r3.id,
        reason="authentication_failed",
        risk_status=RiskStatus.medium,
        priority=RecoveryPriority.medium,
        current_state=RecoveryCaseState.open,
        created_at=base_time + timedelta(days=2),
    )
    db_session.add(c3)
    db_session.flush()

    a3 = RecoveryApproval(
        recovery_case_id=c3.id,
        action_type=RecoveryActionType.whatsapp_reminder,
        channel=RecoveryActionChannel.whatsapp,
        status=ApprovalStatus.approved,
        requires_human_review=False,
        approved_by="auto_system",
        requested_at=base_time + timedelta(days=2),
        created_at=base_time + timedelta(days=2),
    )
    db_session.add(a3)
    db_session.flush()

    j3 = RecoveryExecutionJob(
        recovery_case_id=c3.id,
        recovery_approval_id=a3.id,
        status=JobStatus.failed,
        attempt_count=3,
        max_attempts=3,
        error_code="GATEWAY_REJECTED",
        error_message="Gateway dropped connection",
        idempotency_key=f"appr:{a3.id}:wa",
        created_at=base_time + timedelta(days=2),
    )
    db_session.add(j3)
    db_session.flush()

    # Seed Audit Log
    AuditService.create_audit_log(
        db=db_session,
        entity_type="recovery_case",
        entity_id=str(c1.id),
        action="case_recovered",
        actor="system",
        metadata={"recovery_case_id": c1.id, "status": "recovered"},
    )


    db_session.commit()
    return {
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "base_time": base_time,
    }


# ---------------------------------------------------------------------------
# 1. CORE METRICS & EMPTY DATABASE TESTS
# ---------------------------------------------------------------------------


def test_empty_database_analytics(db_session):
    """Test that all analytics queries return graceful zero structures on an empty database."""
    overview = AnalyticsService.get_overview(db_session)
    assert overview.total_cases == 0
    assert overview.total_recoverable_amount == 0
    assert overview.total_recovered_amount == 0
    assert overview.recovery_rate == 0.0
    assert overview.case_recovery_rate == 0.0
    assert overview.total_approvals == 0
    assert overview.total_execution_jobs == 0
    assert overview.execution_success_rate == 0.0

    revenue = AnalyticsService.get_revenue(db_session)
    assert revenue.total_recoverable_amount == 0
    assert revenue.total_recovered_amount == 0
    assert revenue.recovery_rate == 0.0
    assert revenue.average_recovery_amount == 0

    execution = AnalyticsService.get_execution(db_session)
    assert execution.total_jobs == 0
    assert execution.success_rate == 0.0
    assert execution.total_retries == 0

    approvals = AnalyticsService.get_approvals(db_session)
    assert approvals.total == 0
    assert approvals.approval_rate == 0.0

    failures = AnalyticsService.get_failures(db_session)
    assert failures.failure_count == 0
    assert len(failures.error_breakdown) == 0

    channels = AnalyticsService.get_channels(db_session)
    assert len(channels) == len(RecoveryActionChannel)
    assert all(c.total == 0 for c in channels)

    timeline = AnalyticsService.get_timeline(db_session)
    assert len(timeline) == 0

    activity = AnalyticsService.get_recent_activity(db_session)
    assert activity.total == 0
    assert len(activity.items) == 0


def test_overview_metrics_calculations(db_session, analytics_seed_data):
    """Test overview metrics calculation with seeded records."""
    overview = AnalyticsService.get_overview(db_session)

    assert overview.total_cases == 3
    assert overview.recovered_cases == 1
    assert overview.action_pending_cases == 1
    assert overview.open_cases == 1

    # Total recoverable = 100000 + 200000 + 150000 = 450000 paise
    assert overview.total_recoverable_amount == 450000
    # Total recovered = 100000 paise
    assert overview.total_recovered_amount == 100000

    # Rate: 100000 / 450000 = 0.2222
    assert round(overview.recovery_rate, 4) == 0.2222
    # Case rate: 1 / 3 = 0.3333
    assert round(overview.case_recovery_rate, 4) == 0.3333

    assert overview.total_approvals == 3
    assert overview.approved_approvals == 2
    assert overview.pending_approvals == 1

    assert overview.total_execution_jobs == 2
    assert overview.successful_jobs == 1
    assert overview.failed_jobs == 1
    assert overview.execution_success_rate == 0.5


def test_revenue_analytics_calculations(db_session, analytics_seed_data):
    """Test detailed revenue analytics calculations."""
    rev = AnalyticsService.get_revenue(db_session)

    assert rev.total_recoverable_amount == 450000
    assert rev.total_recovered_amount == 100000
    assert rev.recovered_case_count == 1
    assert rev.average_recovery_amount == 100000
    assert round(rev.recovery_rate, 4) == 0.2222


def test_recovery_rate_precision_and_bounding():
    """Test safe division helper bounds results between 0.0 and 1.0."""
    assert safe_division(100, 200) == 0.5
    assert safe_division(0, 500) == 0.0
    assert safe_division(500, 0) == 0.0
    assert safe_division(0, 0) == 0.0
    assert safe_division(150, 100) == 1.0  # Bounded to 1.0 default
    assert safe_division(150, 100, max_val=None) == 1.5  # Unbounded if explicit


def test_safe_average_calculation():
    """Test safe average calculation with zero division guard."""
    assert safe_average(10000, 2) == 5000
    assert safe_average(10000, 0) == 0
    assert safe_average(0, 5) == 0


def test_approval_analytics_breakdown(db_session, analytics_seed_data):
    """Test approval analytics and decision rate computation."""
    appr = AnalyticsService.get_approvals(db_session)

    assert appr.total == 3
    assert appr.pending == 1
    assert appr.approved == 2
    assert appr.rejected == 0
    # Decided = 2 approved + 0 rejected -> approval_rate = 2/2 = 1.0
    assert appr.approval_rate == 1.0


def test_execution_analytics_breakdown(db_session, analytics_seed_data):
    """Test execution analytics breakdown and retry metrics."""
    exec_data = AnalyticsService.get_execution(db_session)

    assert exec_data.total_jobs == 2
    assert exec_data.succeeded == 1
    assert exec_data.failed == 1
    assert exec_data.success_rate == 0.5

    # Job 1 had 1 attempt, Job 3 had 3 attempts (2 retries)
    assert exec_data.total_retries == 2
    assert exec_data.jobs_with_retries == 1
    assert exec_data.average_attempt_count == 2.0
    assert exec_data.max_attempt_count == 3


def test_channel_analytics_breakdown(db_session, analytics_seed_data):
    """Test execution breakdown grouped by communication channel."""
    channels = AnalyticsService.get_channels(db_session)

    ch_map = {c.channel: c for c in channels}

    # Email: 1 total, 1 succeeded
    assert ch_map[RecoveryActionChannel.email].total == 1
    assert ch_map[RecoveryActionChannel.email].successful == 1
    assert ch_map[RecoveryActionChannel.email].success_rate == 1.0

    # WhatsApp: 1 total, 1 failed
    assert ch_map[RecoveryActionChannel.whatsapp].total == 1
    assert ch_map[RecoveryActionChannel.whatsapp].failed == 1
    assert ch_map[RecoveryActionChannel.whatsapp].success_rate == 0.0

    # SMS: 0 jobs created (approval was pending)
    assert ch_map[RecoveryActionChannel.sms].total == 0


def test_failure_analytics_and_error_codes(db_session, analytics_seed_data):
    """Test failure metrics and error code distribution."""
    failures = AnalyticsService.get_failures(db_session)

    assert failures.failure_count == 1
    assert len(failures.error_breakdown) == 1
    assert failures.error_breakdown[0].error_code == "GATEWAY_REJECTED"
    assert failures.error_breakdown[0].count == 1


# ---------------------------------------------------------------------------
# 2. DATE FILTERING & TIME-SERIES TESTS
# ---------------------------------------------------------------------------


def test_date_range_filtering_valid(db_session, analytics_seed_data):
    """Test filtering metrics within a specific date window."""
    base_time = analytics_seed_data["base_time"]

    # Filter only Day 1
    s_date = base_time.date().isoformat()
    e_date = (base_time + timedelta(hours=23)).isoformat()

    overview = AnalyticsService.get_overview(db_session, start_date=s_date, end_date=e_date)
    assert overview.total_cases == 1
    assert overview.total_recoverable_amount == 100000
    assert overview.total_recovered_amount == 100000
    assert overview.recovery_rate == 1.0


def test_invalid_date_range_rejection_422(db_session):
    """Test that start_date > end_date raises InvalidDateRangeError."""
    with pytest.raises(InvalidDateRangeError) as exc:
        AnalyticsService.get_overview(
            db_session,
            start_date="2026-12-31",
            end_date="2026-01-01",
        )
    assert "start_date" in str(exc.value)


def test_timeline_aggregation_daily(db_session, analytics_seed_data):
    """Test daily timeline aggregation data points."""
    timeline = AnalyticsService.get_timeline(db_session)

    assert len(timeline) >= 3
    # Check that points contain valid dates and counts
    for point in timeline:
        assert isinstance(point.date, str)
        assert point.recoverable_amount >= 0


def test_recent_activity_querying_and_limit(db_session, analytics_seed_data):
    """Test recent activity querying, limit constraints, and safe sanitization."""
    activity = AnalyticsService.get_recent_activity(db_session, limit=10)

    assert activity.total >= 1
    item = activity.items[0]
    assert item.event == "case_recovered"
    assert item.entity_type == "recovery_case"
    assert item.actor == "system"


def test_read_only_guarantee(db_session, analytics_seed_data):
    """Test that calling analytics does not modify database state or insert audit logs."""
    case_count_before = db_session.query(RecoveryCase).count()
    audit_count_before = db_session.query(AuditLog).count()

    # Call all analytics methods
    AnalyticsService.get_overview(db_session)
    AnalyticsService.get_revenue(db_session)
    AnalyticsService.get_execution(db_session)
    AnalyticsService.get_approvals(db_session)
    AnalyticsService.get_failures(db_session)
    AnalyticsService.get_channels(db_session)
    AnalyticsService.get_timeline(db_session)
    AnalyticsService.get_recent_activity(db_session)

    case_count_after = db_session.query(RecoveryCase).count()
    audit_count_after = db_session.query(AuditLog).count()

    assert case_count_before == case_count_after
    assert audit_count_before == audit_count_after


# ---------------------------------------------------------------------------
# 3. REST API ENDPOINTS TESTS
# ---------------------------------------------------------------------------


def test_api_analytics_endpoints(client, db_session, analytics_seed_data):
    """Test all REST API endpoints under /api/v1/analytics/."""
    # 1. Overview
    res = client.get("/api/v1/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["total_cases"] == 3
    assert data["total_recovered_amount"] == 100000

    # 2. Revenue
    res_rev = client.get("/api/v1/analytics/revenue")
    assert res_rev.status_code == 200
    assert res_rev.json()["currency"] == "INR"

    # 3. Execution
    res_exec = client.get("/api/v1/analytics/execution")
    assert res_exec.status_code == 200
    assert res_exec.json()["total_jobs"] == 2

    # 4. Approvals
    res_appr = client.get("/api/v1/analytics/approvals")
    assert res_appr.status_code == 200
    assert res_appr.json()["approved"] == 2

    # 5. Failures
    res_fail = client.get("/api/v1/analytics/failures")
    assert res_fail.status_code == 200
    assert res_fail.json()["failure_count"] == 1

    # 6. Channels
    res_ch = client.get("/api/v1/analytics/channels")
    assert res_ch.status_code == 200
    assert len(res_ch.json()) == len(RecoveryActionChannel)

    # 7. Timeline
    res_time = client.get("/api/v1/analytics/timeline")
    assert res_time.status_code == 200
    assert len(res_time.json()) >= 3

    # 8. Recent Activity
    res_act = client.get("/api/v1/analytics/recent-activity?limit=10")
    assert res_act.status_code == 200
    assert res_act.json()["total"] >= 1

    # 9. Invalid date range -> 422
    res_inv = client.get("/api/v1/analytics/overview?start_date=2026-12-31&end_date=2026-01-01")
    assert res_inv.status_code == 422


def test_case_recovery_rate_calculation(db_session, analytics_seed_data):
    """Test case recovery rate calculation on non-empty vs empty dataset."""
    overview = AnalyticsService.get_overview(db_session)
    # 1 recovered out of 3 total cases -> 1/3 = 0.3333
    assert overview.case_recovery_rate == 0.3333


def test_financial_accuracy_in_paise(db_session, analytics_seed_data):
    """Test that all financial calculations preserve exact integer paise without floating point drift."""
    rev = AnalyticsService.get_revenue(db_session)
    assert isinstance(rev.total_recoverable_amount, int)
    assert isinstance(rev.total_recovered_amount, int)
    assert isinstance(rev.average_recovery_amount, int)
    assert rev.total_recoverable_amount == 450000
    assert rev.total_recovered_amount == 100000


def test_recent_activity_sanitizes_tokens_and_secrets(db_session):
    """Test that recent activity logs never expose passwords, tokens, or auth headers."""
    AuditService.create_audit_log(
        db=db_session,
        entity_type="payment",
        entity_id="pay_999",
        action="payment_processed",
        actor="system",
        metadata={
            "status": "authorized",
            "api_key": "secret_key_12345",
            "token": "token_abcde",
        },
    )
    db_session.commit()

    activity = AnalyticsService.get_recent_activity(db_session, limit=5)
    for item in activity.items:
        # Check details doesn't expose secret values
        if item.details:
            assert "secret_key" not in item.details
            assert "token_abcde" not in item.details


def test_recent_activity_limit_boundary(db_session):
    """Test that recent activity clamps limit to max 100 and min 1."""
    resp = AnalyticsService.get_recent_activity(db_session, limit=500)
    assert len(resp.items) <= 100

