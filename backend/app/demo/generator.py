"""
Deterministic synthetic dataset generator for RecoverAI.

Generates realistic Indian merchant payment failure data across payments, revenues,
recovery cases, approvals, background execution jobs, and audit trails.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.demo.schemas import DemoResetResponse, DemoSeedResponse
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
from app.models.payment import Payment, PaymentEvent
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord
from app.services.audit_service import AuditService

FAILURE_REASONS = [
    "insufficient_funds",
    "card_network_timeout",
    "3ds_authentication_failed",
    "upi_pin_expired",
    "do_not_honor",
    "daily_limit_exceeded",
]

CHANNELS = [
    (RecoveryActionChannel.email, RecoveryActionType.email_reminder),
    (RecoveryActionChannel.sms, RecoveryActionType.sms_reminder),
    (RecoveryActionChannel.whatsapp, RecoveryActionType.whatsapp_reminder),
    (RecoveryActionChannel.webhook, RecoveryActionType.webhook_ping),
]

ERROR_CODES = [
    ("GATEWAY_TIMEOUT", True),
    ("INVALID_RECIPIENT", False),
    ("NETWORK_CONGESTION", True),
    ("USER_OPTED_OUT", False),
    ("RATE_LIMIT_EXCEEDED", True),
]


def reset_database_records(db: Session) -> DemoResetResponse:
    """Safely purges database records in proper dependency order."""
    j_count = db.execute(delete(RecoveryExecutionJob)).rowcount or 0
    appr_count = db.execute(delete(RecoveryApproval)).rowcount or 0
    act_count = db.execute(delete(RecoveryAction)).rowcount or 0
    case_count = db.execute(delete(RecoveryCase)).rowcount or 0
    rev_count = db.execute(delete(RevenueRecord)).rowcount or 0
    ev_count = db.execute(delete(PaymentEvent)).rowcount or 0
    pay_count = db.execute(delete(Payment)).rowcount or 0
    audit_count = db.execute(delete(AuditLog)).rowcount or 0

    db.commit()

    return DemoResetResponse(
        payments_deleted=pay_count,
        cases_deleted=case_count,
        jobs_deleted=j_count,
        audit_logs_deleted=audit_count,
        message=f"Purged {pay_count} payments, {case_count} cases, {j_count} execution jobs, and {audit_count} audit logs.",
    )


def generate_synthetic_dataset(
    db: Session,
    count: int = 50,
    seed: int = 42,
    reset: bool = False,
) -> DemoSeedResponse:
    """
    Generates a deterministic synthetic dataset spanning the last 30 days.

    Args:
        db: SQLAlchemy session.
        count: Number of cases to generate (default 50).
        seed: Random seed for 100% deterministic reproducibility.
        reset: If True, purges existing records before generation.
    """
    if reset:
        reset_database_records(db)

    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    payments_created = 0
    revenue_created = 0
    cases_created = 0
    approvals_created = 0
    jobs_created = 0
    audit_created = 0
    total_recoverable = 0
    total_recovered = 0

    methods = [PaymentMethod.card, PaymentMethod.upi, PaymentMethod.netbanking]
    priorities = [RecoveryPriority.low, RecoveryPriority.medium, RecoveryPriority.high, RecoveryPriority.urgent]

    for i in range(1, count + 1):
        # 1. Distribute timestamps across last 28 days
        # Cluster some items today, last 7 days, and last 30 days
        days_ago = rng.choice([0, 0, 1, 2, 3, 4, 5, 6, 7, 10, 14, 18, 21, 25, 28])
        hours_ago = rng.randint(1, 23)
        created_dt = now - timedelta(days=days_ago, hours=hours_ago)

        # 2. Payment details
        amount_paise = rng.choice([50000, 100000, 150000, 249900, 399900, 499900, 750000, 999900, 1500000])
        total_recoverable += amount_paise

        is_recovered = (i % 3 == 0) or (i % 7 == 0)  # ~40% recovery rate
        payment_status = PaymentStatus.captured if is_recovered else PaymentStatus.failed

        payment = Payment(
            razorpay_payment_id=f"pay_demo_{seed}_{i:04d}",
            razorpay_order_id=f"order_demo_{seed}_{i:04d}",
            amount=amount_paise,
            currency="INR",
            status=payment_status,
            method=rng.choice(methods),
            customer_email=f"demo_customer_{i}@demo-store.example",
            customer_reference=f"+9198{rng.randint(10000000, 99999999)}",
            created_at=created_dt,
            updated_at=created_dt,
        )
        db.add(payment)
        db.flush()
        payments_created += 1

        # 3. Revenue record
        rev_status = RevenueStatus.recovered if is_recovered else RevenueStatus.at_risk
        if is_recovered:
            total_recovered += amount_paise

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=amount_paise,
            recoverable_amount=0 if is_recovered else amount_paise,
            currency="INR",
            status=rev_status,
            created_at=created_dt,
            updated_at=created_dt,
        )
        db.add(revenue)
        db.flush()
        revenue_created += 1

        # 4. Recovery Case
        if is_recovered:
            case_state = RecoveryCaseState.recovered
        else:
            case_state = rng.choice([
                RecoveryCaseState.open,
                RecoveryCaseState.action_pending,
                RecoveryCaseState.recovering,
                RecoveryCaseState.closed,
            ])

        risk = RiskStatus.high if amount_paise >= 750000 else (RiskStatus.medium if amount_paise >= 250000 else RiskStatus.low)
        reason = rng.choice(FAILURE_REASONS)

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason=reason,
            risk_status=risk,
            priority=rng.choice(priorities),
            current_state=case_state,
            created_at=created_dt,
            updated_at=created_dt,
        )
        db.add(case)
        db.flush()
        cases_created += 1

        # 5. Recovery Approval & Execution Job
        channel, action_type = rng.choice(CHANNELS)
        requires_human = (risk == RiskStatus.high)

        if case_state in [RecoveryCaseState.action_pending] and requires_human:
            approval_status = ApprovalStatus.pending
            approved_by = None
            approved_at = None
        elif case_state == RecoveryCaseState.closed:
            approval_status = ApprovalStatus.rejected
            approved_by = "demo_supervisor"
            approved_at = created_dt
        else:
            approval_status = ApprovalStatus.approved
            approved_by = "auto_system" if not requires_human else "demo_supervisor"
            approved_at = created_dt

        approval = RecoveryApproval(
            recovery_case_id=case.id,
            action_type=action_type,
            channel=channel,
            status=approval_status,
            requires_human_review=requires_human,
            approved_by=approved_by,
            requested_at=created_dt,
            approved_at=approved_at,
            created_at=created_dt,
            updated_at=created_dt,
        )
        db.add(approval)
        db.flush()
        approvals_created += 1

        # 6. Execution Job (for approved cases)
        if approval_status == ApprovalStatus.approved:
            if is_recovered or case_state == RecoveryCaseState.recovering:
                job_status = JobStatus.succeeded
                attempts = 1
                err_code = None
                err_msg = None
            elif case_state == RecoveryCaseState.open:
                job_status = JobStatus.queued
                attempts = 0
                err_code = None
                err_msg = None
            else:
                # Failed or retry scheduled
                err_code, is_retryable = rng.choice(ERROR_CODES)
                job_status = JobStatus.retry_scheduled if is_retryable else JobStatus.failed
                attempts = rng.randint(1, 3)
                err_msg = f"Simulated provider failure: {err_code}"

            job = RecoveryExecutionJob(
                recovery_case_id=case.id,
                recovery_approval_id=approval.id,
                status=job_status,
                attempt_count=attempts,
                max_attempts=3,
                idempotency_key=f"demo_job:{seed}:{i}:{channel.value}",
                error_code=err_code,
                error_message=err_msg,
                result={"success": job_status == JobStatus.succeeded, "channel": channel.value},
                scheduled_at=created_dt,
                started_at=created_dt if attempts > 0 else None,
                completed_at=created_dt if job_status in [JobStatus.succeeded, JobStatus.failed] else None,
                created_at=created_dt,
                updated_at=created_dt,
            )
            db.add(job)
            db.flush()
            jobs_created += 1

        # 7. Audit log
        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(case.id),
            action="case_created" if not is_recovered else "case_recovered",
            actor="demo_system",
            metadata={"recovery_case_id": case.id, "amount_paise": amount_paise, "channel": channel.value},
        )
        audit_created += 1

    db.commit()

    return DemoSeedResponse(
        seed=seed,
        payments_created=payments_created,
        revenue_records_created=revenue_created,
        cases_created=cases_created,
        approvals_created=approvals_created,
        jobs_created=jobs_created,
        audit_logs_created=audit_created,
        total_recoverable_amount=total_recoverable,
        total_recovered_amount=total_recovered,
        message=f"Successfully generated {cases_created} synthetic recovery cases ({total_recovered / total_recoverable * 100:.1f}% recovery rate) across the last 30 days." if total_recoverable > 0 else f"Successfully generated {cases_created} synthetic recovery cases (no recoverable amounts) across the last 30 days.",
    )
