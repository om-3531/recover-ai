"""
Database query and aggregation logic for Analytics and Metrics.

Strictly READ-ONLY queries performing database-level aggregations (COUNT, SUM, GROUP BY).
"""

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from app.analytics.metrics import ensure_utc, safe_average, safe_division
from app.analytics.schemas import (
    ApprovalAnalytics,
    ChannelAnalytics,
    ErrorBreakdownItem,
    ExecutionAnalytics,
    FailureAnalytics,
    OverviewMetrics,
    RecentActivityItem,
    RevenueAnalytics,
    TimelinePoint,
)
from app.models.approval import RecoveryApproval
from app.models.audit import AuditLog
from app.models.enums import (
    ApprovalStatus,
    JobStatus,
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryCaseState,
    RevenueStatus,
)
from app.models.job import RecoveryExecutionJob
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord


def get_overview_metrics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> OverviewMetrics:
    """Computes high-level overview metrics across cases, revenue, approvals, and jobs."""
    # 1. Recovery Case status breakdown
    case_query = select(
        RecoveryCase.current_state,
        func.count(RecoveryCase.id),
    ).group_by(RecoveryCase.current_state)

    if start_date:
        case_query = case_query.where(RecoveryCase.created_at >= start_date)
    if end_date:
        case_query = case_query.where(RecoveryCase.created_at <= end_date)

    case_counts = dict(db.execute(case_query).all())
    total_cases = sum(case_counts.values())
    open_cases = case_counts.get(RecoveryCaseState.open, 0)
    action_pending_cases = case_counts.get(RecoveryCaseState.action_pending, 0)
    recovering_cases = case_counts.get(RecoveryCaseState.recovering, 0)
    recovered_cases = case_counts.get(RecoveryCaseState.recovered, 0)
    closed_cases = case_counts.get(RecoveryCaseState.closed, 0)
    failed_cases = case_counts.get(RecoveryCaseState.failed, 0)

    # 2. Revenue totals
    rev_query = select(
        func.coalesce(func.sum(RevenueRecord.recoverable_amount), 0),
        func.coalesce(
            func.sum(
                case(
                    (RevenueRecord.status == RevenueStatus.recovered, RevenueRecord.gross_amount),
                    else_=0,
                )
            ),
            0,
        ),
    )
    if start_date:
        rev_query = rev_query.where(RevenueRecord.created_at >= start_date)
    if end_date:
        rev_query = rev_query.where(RevenueRecord.created_at <= end_date)

    total_recoverable, total_recovered = db.execute(rev_query).one()
    recovery_rate = safe_division(total_recovered, total_recoverable)
    case_recovery_rate = safe_division(recovered_cases, total_cases)

    # 3. Approval counts
    appr_query = select(
        RecoveryApproval.status,
        func.count(RecoveryApproval.id),
    ).group_by(RecoveryApproval.status)

    if start_date:
        appr_query = appr_query.where(RecoveryApproval.requested_at >= start_date)
    if end_date:
        appr_query = appr_query.where(RecoveryApproval.requested_at <= end_date)

    appr_counts = dict(db.execute(appr_query).all())
    total_approvals = sum(appr_counts.values())
    pending_approvals = appr_counts.get(ApprovalStatus.pending, 0)
    approved_approvals = appr_counts.get(ApprovalStatus.approved, 0)
    rejected_approvals = appr_counts.get(ApprovalStatus.rejected, 0)

    # 4. Job counts
    job_query = select(
        RecoveryExecutionJob.status,
        func.count(RecoveryExecutionJob.id),
    ).group_by(RecoveryExecutionJob.status)

    if start_date:
        job_query = job_query.where(RecoveryExecutionJob.created_at >= start_date)
    if end_date:
        job_query = job_query.where(RecoveryExecutionJob.created_at <= end_date)

    job_counts = dict(db.execute(job_query).all())
    total_jobs = sum(job_counts.values())
    successful_jobs = job_counts.get(JobStatus.succeeded, 0)
    failed_jobs = job_counts.get(JobStatus.failed, 0)
    retry_scheduled_jobs = job_counts.get(JobStatus.retry_scheduled, 0)

    completed_jobs = successful_jobs + failed_jobs
    execution_success_rate = safe_division(successful_jobs, completed_jobs if completed_jobs > 0 else total_jobs)

    return OverviewMetrics(
        total_cases=total_cases,
        open_cases=open_cases,
        action_pending_cases=action_pending_cases,
        recovering_cases=recovering_cases,
        recovered_cases=recovered_cases,
        closed_cases=closed_cases,
        failed_cases=failed_cases,
        total_recoverable_amount=int(total_recoverable),
        total_recovered_amount=int(total_recovered),
        recovery_rate=recovery_rate,
        case_recovery_rate=case_recovery_rate,
        total_approvals=total_approvals,
        pending_approvals=pending_approvals,
        approved_approvals=approved_approvals,
        rejected_approvals=rejected_approvals,
        total_execution_jobs=total_jobs,
        successful_jobs=successful_jobs,
        failed_jobs=failed_jobs,
        retry_scheduled_jobs=retry_scheduled_jobs,
        execution_success_rate=execution_success_rate,
        generated_at=datetime.now(timezone.utc),
    )


def get_revenue_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> RevenueAnalytics:
    """Calculates financial totals, recovery rates, and averages."""
    rev_query = select(
        func.coalesce(func.sum(RevenueRecord.recoverable_amount), 0),
        func.coalesce(
            func.sum(
                case(
                    (RevenueRecord.status == RevenueStatus.recovered, RevenueRecord.gross_amount),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    (RevenueRecord.status == RevenueStatus.recovered, 1),
                    else_=0,
                )
            ),
            0,
        ),
    )
    if start_date:
        rev_query = rev_query.where(RevenueRecord.created_at >= start_date)
    if end_date:
        rev_query = rev_query.where(RevenueRecord.created_at <= end_date)

    total_recoverable, total_recovered, recovered_count = db.execute(rev_query).one()
    recovery_rate = safe_division(total_recovered, total_recoverable)
    average_recovery = safe_average(total_recovered, recovered_count)

    return RevenueAnalytics(
        total_recoverable_amount=int(total_recoverable),
        total_recovered_amount=int(total_recovered),
        recovery_rate=recovery_rate,
        average_recovery_amount=average_recovery,
        recovered_case_count=int(recovered_count),
        currency="INR",
    )


def get_execution_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ExecutionAnalytics:
    """Calculates execution job lifecycle, retry metrics, and channel breakdowns."""
    # 1. Job statuses
    job_query = select(
        RecoveryExecutionJob.status,
        func.count(RecoveryExecutionJob.id),
    ).group_by(RecoveryExecutionJob.status)

    if start_date:
        job_query = job_query.where(RecoveryExecutionJob.created_at >= start_date)
    if end_date:
        job_query = job_query.where(RecoveryExecutionJob.created_at <= end_date)

    job_counts = dict(db.execute(job_query).all())
    total_jobs = sum(job_counts.values())
    queued = job_counts.get(JobStatus.queued, 0)
    running = job_counts.get(JobStatus.running, 0)
    succeeded = job_counts.get(JobStatus.succeeded, 0)
    failed = job_counts.get(JobStatus.failed, 0)
    retry_scheduled = job_counts.get(JobStatus.retry_scheduled, 0)
    cancelled = job_counts.get(JobStatus.cancelled, 0)

    completed = succeeded + failed
    success_rate = safe_division(succeeded, completed if completed > 0 else total_jobs)

    # 2. Retry statistics
    retry_query = select(
        func.coalesce(
            func.sum(
                case(
                    (RecoveryExecutionJob.attempt_count > 1, RecoveryExecutionJob.attempt_count - 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    (RecoveryExecutionJob.attempt_count > 1, 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(func.avg(RecoveryExecutionJob.attempt_count), 0.0),
        func.coalesce(func.max(RecoveryExecutionJob.attempt_count), 0),
    )
    if start_date:
        retry_query = retry_query.where(RecoveryExecutionJob.created_at >= start_date)
    if end_date:
        retry_query = retry_query.where(RecoveryExecutionJob.created_at <= end_date)

    total_retries, jobs_with_retries, avg_attempts, max_attempts = db.execute(retry_query).one()

    # 3. Channel breakdown
    channels = get_channel_analytics(db, start_date=start_date, end_date=end_date)

    return ExecutionAnalytics(
        total_jobs=total_jobs,
        queued=queued,
        running=running,
        succeeded=succeeded,
        failed=failed,
        retry_scheduled=retry_scheduled,
        cancelled=cancelled,
        success_rate=success_rate,
        total_retries=int(total_retries),
        jobs_with_retries=int(jobs_with_retries),
        average_attempt_count=round(float(avg_attempts), 2),
        max_attempt_count=int(max_attempts),
        channels=channels,
    )


def get_approval_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ApprovalAnalytics:
    """Calculates approval statuses and decision rates."""
    appr_query = select(
        RecoveryApproval.status,
        func.count(RecoveryApproval.id),
    ).group_by(RecoveryApproval.status)

    if start_date:
        appr_query = appr_query.where(RecoveryApproval.requested_at >= start_date)
    if end_date:
        appr_query = appr_query.where(RecoveryApproval.requested_at <= end_date)

    counts = dict(db.execute(appr_query).all())
    total = sum(counts.values())
    pending = counts.get(ApprovalStatus.pending, 0)
    approved = counts.get(ApprovalStatus.approved, 0)
    rejected = counts.get(ApprovalStatus.rejected, 0)
    expired = counts.get(ApprovalStatus.expired, 0)
    cancelled = counts.get(ApprovalStatus.cancelled, 0)

    decided = approved + rejected + expired + cancelled
    approval_rate = safe_division(approved, decided if decided > 0 else total)

    return ApprovalAnalytics(
        total=total,
        pending=pending,
        approved=approved,
        rejected=rejected,
        expired=expired,
        cancelled=cancelled,
        approval_rate=approval_rate,
    )


def get_failure_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> FailureAnalytics:
    """Analyzes execution failure errors, retryable vs permanent errors."""
    # Count failed and retry scheduled jobs
    fail_query = select(
        func.coalesce(
            func.sum(
                case(
                    (RecoveryExecutionJob.status.in_([JobStatus.failed, JobStatus.retry_scheduled]), 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    (RecoveryExecutionJob.status == JobStatus.retry_scheduled, 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    (RecoveryExecutionJob.status == JobStatus.failed, 1),
                    else_=0,
                )
            ),
            0,
        ),
    )
    if start_date:
        fail_query = fail_query.where(RecoveryExecutionJob.created_at >= start_date)
    if end_date:
        fail_query = fail_query.where(RecoveryExecutionJob.created_at <= end_date)

    total_failures, retryable, non_retryable = db.execute(fail_query).one()

    # Error code grouping
    err_query = (
        select(
            func.coalesce(RecoveryExecutionJob.error_code, "UNKNOWN").label("err_code"),
            func.count(RecoveryExecutionJob.id),
        )
        .where(RecoveryExecutionJob.status.in_([JobStatus.failed, JobStatus.retry_scheduled]))
        .group_by("err_code")
        .order_by(func.count(RecoveryExecutionJob.id).desc())
    )
    if start_date:
        err_query = err_query.where(RecoveryExecutionJob.created_at >= start_date)
    if end_date:
        err_query = err_query.where(RecoveryExecutionJob.created_at <= end_date)

    err_results = db.execute(err_query).all()
    error_breakdown = [
        ErrorBreakdownItem(error_code=row[0], count=row[1]) for row in err_results
    ]

    return FailureAnalytics(
        failure_count=int(total_failures),
        retryable_failure_count=int(retryable),
        non_retryable_failure_count=int(non_retryable),
        error_breakdown=error_breakdown,
    )


def get_channel_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[ChannelAnalytics]:
    """Computes execution metrics grouped by communication channel."""
    # Query joining RecoveryExecutionJob and RecoveryApproval to get channel
    query = (
        select(
            RecoveryApproval.channel,
            func.count(RecoveryExecutionJob.id).label("total"),
            func.sum(
                case(
                    (RecoveryExecutionJob.status == JobStatus.succeeded, 1),
                    else_=0,
                )
            ).label("succeeded"),
            func.sum(
                case(
                    (RecoveryExecutionJob.status == JobStatus.failed, 1),
                    else_=0,
                )
            ).label("failed"),
        )
        .join(RecoveryApproval, RecoveryExecutionJob.recovery_approval_id == RecoveryApproval.id)
        .group_by(RecoveryApproval.channel)
    )

    if start_date:
        query = query.where(RecoveryExecutionJob.created_at >= start_date)
    if end_date:
        query = query.where(RecoveryExecutionJob.created_at <= end_date)

    channel_data = {
        row.channel: (row.total, row.succeeded or 0, row.failed or 0)
        for row in db.execute(query).all()
    }

    results: List[ChannelAnalytics] = []
    # Guarantee all standard channels are present in output
    for ch in RecoveryActionChannel:
        if ch in channel_data:
            total, succ, fail = channel_data[ch]
            rate = safe_division(succ, total)
            results.append(
                ChannelAnalytics(
                    channel=ch,
                    total=total,
                    successful=succ,
                    failed=fail,
                    success_rate=rate,
                )
            )
        else:
            results.append(
                ChannelAnalytics(
                    channel=ch,
                    total=0,
                    successful=0,
                    failed=0,
                    success_rate=0.0,
                )
            )

    return results


def get_timeline_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[TimelinePoint]:
    """Aggregates daily time-series recovery events and revenue metrics."""
    # 1. Cases created and recovered by date
    case_query = select(
        func.date(RecoveryCase.created_at).label("d"),
        func.count(RecoveryCase.id).label("cases_created"),
        func.sum(
            case(
                (RecoveryCase.current_state == RecoveryCaseState.recovered, 1),
                else_=0,
            )
        ).label("cases_recovered"),
    ).group_by(func.date(RecoveryCase.created_at))

    if start_date:
        case_query = case_query.where(RecoveryCase.created_at >= start_date)
    if end_date:
        case_query = case_query.where(RecoveryCase.created_at <= end_date)

    cases_by_date = {
        str(row.d): (row.cases_created, row.cases_recovered or 0)
        for row in db.execute(case_query).all()
        if row.d is not None
    }

    # 2. Revenue recoverable and recovered by date
    rev_query = select(
        func.date(RevenueRecord.created_at).label("d"),
        func.coalesce(func.sum(RevenueRecord.recoverable_amount), 0).label("recoverable"),
        func.coalesce(
            func.sum(
                case(
                    (RevenueRecord.status == RevenueStatus.recovered, RevenueRecord.gross_amount),
                    else_=0,
                )
            ),
            0,
        ).label("recovered"),
    ).group_by(func.date(RevenueRecord.created_at))

    if start_date:
        rev_query = rev_query.where(RevenueRecord.created_at >= start_date)
    if end_date:
        rev_query = rev_query.where(RevenueRecord.created_at <= end_date)

    rev_by_date = {
        str(row.d): (int(row.recoverable), int(row.recovered))
        for row in db.execute(rev_query).all()
        if row.d is not None
    }

    # 3. Executions succeeded and failed by date
    job_query = select(
        func.date(RecoveryExecutionJob.created_at).label("d"),
        func.sum(
            case(
                (RecoveryExecutionJob.status == JobStatus.succeeded, 1),
                else_=0,
            )
        ).label("succeeded"),
        func.sum(
            case(
                (RecoveryExecutionJob.status == JobStatus.failed, 1),
                else_=0,
            )
        ).label("failed"),
    ).group_by(func.date(RecoveryExecutionJob.created_at))


    if start_date:
        job_query = job_query.where(RecoveryExecutionJob.created_at >= start_date)
    if end_date:
        job_query = job_query.where(RecoveryExecutionJob.created_at <= end_date)

    jobs_by_date = {
        str(row.d): (row.succeeded or 0, row.failed or 0)
        for row in db.execute(job_query).all()
        if row.d is not None
    }

    # Gather all unique dates
    all_dates = sorted(set(cases_by_date.keys()) | set(rev_by_date.keys()) | set(jobs_by_date.keys()))

    points: List[TimelinePoint] = []
    for d_str in all_dates:
        cc, cr = cases_by_date.get(d_str, (0, 0))
        rec_able, rec_ed = rev_by_date.get(d_str, (0, 0))
        succ_j, fail_j = jobs_by_date.get(d_str, (0, 0))
        rate = safe_division(rec_ed, rec_able)

        points.append(
            TimelinePoint(
                date=d_str,
                cases_created=cc,
                cases_recovered=cr,
                recoverable_amount=rec_able,
                recovered_amount=rec_ed,
                successful_executions=succ_j,
                failed_executions=fail_j,
                recovery_rate=rate,
            )
        )

    return points


def get_recent_activity(
    db: Session,
    limit: int = 20,
) -> List[RecentActivityItem]:
    """Fetches recent audit log activities sanitized of any sensitive information."""
    safe_limit = max(1, min(100, limit))

    query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(safe_limit)
    audit_logs = db.execute(query).scalars().all()

    items: List[RecentActivityItem] = []
    for log in audit_logs:
        case_id: Optional[int] = None
        if log.entity_type == "recovery_case":
            try:
                case_id = int(log.entity_id)
            except (ValueError, TypeError):
                pass
        elif log.event_metadata and "recovery_case_id" in log.event_metadata:
            try:
                case_id = int(log.event_metadata["recovery_case_id"])
            except (ValueError, TypeError):
                pass

        details = None
        if log.event_metadata:
            # Extract safe non-sensitive summary
            if "status" in log.event_metadata:
                details = f"Status: {log.event_metadata['status']}"
            elif "action_type" in log.event_metadata:
                details = f"Action: {log.event_metadata['action_type']}"

        items.append(
            RecentActivityItem(
                id=log.id,
                event=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                case_id=case_id,
                timestamp=ensure_utc(log.timestamp),
                status="success" if "failed" not in log.action else "failure",
                actor=log.actor,
                details=details,
            )
        )

    return items
