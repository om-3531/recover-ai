"""
Analytics REST API endpoints.

Provides read-only aggregated dashboard metrics, financial metrics, job stats, and recent activity.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.schemas import (
    ApprovalAnalytics,
    ChannelAnalytics,
    ExecutionAnalytics,
    FailureAnalytics,
    OverviewMetrics,
    RecentActivityResponse,
    RevenueAnalytics,
    TimelinePoint,
)
from app.analytics.service import AnalyticsService
from app.db.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/overview",
    response_model=OverviewMetrics,
    summary="Get high-level overview metrics",
    description="Returns aggregate totals and rates across recovery cases, revenue, approvals, and execution jobs.",
)
def get_overview_analytics(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format, e.g. 2026-01-01)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format, e.g. 2026-12-31)"),
    db: Session = Depends(get_db),
) -> OverviewMetrics:
    """Retrieve high-level overview metrics."""
    return AnalyticsService.get_overview(db, start_date=start_date, end_date=end_date)


@router.get(
    "/revenue",
    response_model=RevenueAnalytics,
    summary="Get revenue recovery analytics",
    description="Returns recoverable revenue, recovered revenue, recovery rate, and average recovered amounts in paise.",
)
def get_revenue_analytics(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    db: Session = Depends(get_db),
) -> RevenueAnalytics:
    """Retrieve revenue recovery analytics."""
    return AnalyticsService.get_revenue(db, start_date=start_date, end_date=end_date)


@router.get(
    "/execution",
    response_model=ExecutionAnalytics,
    summary="Get background execution analytics",
    description="Returns execution job lifecycle breakdown, retry rates, and channel statistics.",
)
def get_execution_analytics(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    db: Session = Depends(get_db),
) -> ExecutionAnalytics:
    """Retrieve execution analytics."""
    return AnalyticsService.get_execution(db, start_date=start_date, end_date=end_date)


@router.get(
    "/approvals",
    response_model=ApprovalAnalytics,
    summary="Get approval activity analytics",
    description="Returns approval requests breakdown by status and approval decision rate.",
)
def get_approval_analytics(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    db: Session = Depends(get_db),
) -> ApprovalAnalytics:
    """Retrieve approval analytics."""
    return AnalyticsService.get_approvals(db, start_date=start_date, end_date=end_date)


@router.get(
    "/failures",
    response_model=FailureAnalytics,
    summary="Get execution failure breakdown",
    description="Returns failure counts, retryable vs permanent errors, and error code grouping.",
)
def get_failure_analytics(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    db: Session = Depends(get_db),
) -> FailureAnalytics:
    """Retrieve failure analytics."""
    return AnalyticsService.get_failures(db, start_date=start_date, end_date=end_date)


@router.get(
    "/channels",
    response_model=List[ChannelAnalytics],
    summary="Get channel performance metrics",
    description="Returns execution performance breakdown by communication channel (Email, SMS, WhatsApp, Webhook).",
)
def get_channel_analytics(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    db: Session = Depends(get_db),
) -> List[ChannelAnalytics]:
    """Retrieve channel analytics."""
    return AnalyticsService.get_channels(db, start_date=start_date, end_date=end_date)


@router.get(
    "/timeline",
    response_model=List[TimelinePoint],
    summary="Get daily recovery timeline",
    description="Returns daily time-series buckets of cases, recovered revenue, and executions.",
)
def get_timeline_analytics(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    granularity: str = Query("daily", description="Aggregation granularity (default: daily)"),
    db: Session = Depends(get_db),
) -> List[TimelinePoint]:
    """Retrieve daily timeline analytics."""
    return AnalyticsService.get_timeline(db, start_date=start_date, end_date=end_date)


@router.get(
    "/recent-activity",
    response_model=RecentActivityResponse,
    summary="Get recent recovery activity stream",
    description="Returns sanitized audit log events and job executions for dashboard activity feeds.",
)
def get_recent_activity(
    limit: int = Query(20, ge=1, le=100, description="Maximum items to return (1-100)"),
    db: Session = Depends(get_db),
) -> RecentActivityResponse:
    """Retrieve recent activity stream."""
    return AnalyticsService.get_recent_activity(db, limit=limit)
