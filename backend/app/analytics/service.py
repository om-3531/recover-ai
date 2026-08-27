"""
AnalyticsService application orchestration layer.

Provides read-only business metrics, date-range validation, and aggregation dispatch.
"""

from datetime import date, datetime, time, timezone
from typing import List, Optional, Union

from sqlalchemy.orm import Session

from app.analytics.exceptions import InvalidDateRangeError
from app.analytics.metrics import ensure_utc
from app.analytics.queries import (
    get_approval_analytics,
    get_channel_analytics,
    get_execution_analytics,
    get_failure_analytics,
    get_overview_metrics,
    get_recent_activity,
    get_revenue_analytics,
    get_timeline_analytics,
)
from app.analytics.schemas import (
    ApprovalAnalytics,
    ChannelAnalytics,
    ExecutionAnalytics,
    FailureAnalytics,
    OverviewMetrics,
    RecentActivityItem,
    RecentActivityResponse,
    RevenueAnalytics,
    TimelinePoint,
)


class AnalyticsService:
    """Read-only analytics service orchestrating metrics calculation and database queries."""

    @staticmethod
    def _parse_and_validate_dates(
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Parses and validates date inputs, ensuring start_date <= end_date."""
        dt_start: Optional[datetime] = None
        dt_end: Optional[datetime] = None

        if start_date:
            if isinstance(start_date, str):
                try:
                    dt_start = datetime.fromisoformat(start_date)
                except ValueError as e:
                    raise InvalidDateRangeError(f"Invalid start_date format: {e}")
            elif isinstance(start_date, date) and not isinstance(start_date, datetime):
                dt_start = datetime.combine(start_date, time.min)
            else:
                dt_start = start_date
            dt_start = ensure_utc(dt_start)

        if end_date:
            if isinstance(end_date, str):
                try:
                    dt_end = datetime.fromisoformat(end_date)
                except ValueError as e:
                    raise InvalidDateRangeError(f"Invalid end_date format: {e}")
            elif isinstance(end_date, date) and not isinstance(end_date, datetime):
                dt_end = datetime.combine(end_date, time.max)
            else:
                dt_end = end_date
            dt_end = ensure_utc(dt_end)

        if dt_start and dt_end and dt_start > dt_end:
            raise InvalidDateRangeError(
                f"start_date ({dt_start.isoformat()}) must be less than or equal to end_date ({dt_end.isoformat()})"
            )

        return dt_start, dt_end

    @classmethod
    def get_overview(
        cls,
        db: Session,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> OverviewMetrics:
        """Retrieves high-level overview metrics."""
        s, e = cls._parse_and_validate_dates(start_date, end_date)
        return get_overview_metrics(db, start_date=s, end_date=e)

    @classmethod
    def get_revenue(
        cls,
        db: Session,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> RevenueAnalytics:
        """Retrieves revenue recovery metrics."""
        s, e = cls._parse_and_validate_dates(start_date, end_date)
        return get_revenue_analytics(db, start_date=s, end_date=e)

    @classmethod
    def get_execution(
        cls,
        db: Session,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> ExecutionAnalytics:
        """Retrieves background job execution metrics."""
        s, e = cls._parse_and_validate_dates(start_date, end_date)
        return get_execution_analytics(db, start_date=s, end_date=e)

    @classmethod
    def get_approvals(
        cls,
        db: Session,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> ApprovalAnalytics:
        """Retrieves recovery approval decision metrics."""
        s, e = cls._parse_and_validate_dates(start_date, end_date)
        return get_approval_analytics(db, start_date=s, end_date=e)

    @classmethod
    def get_failures(
        cls,
        db: Session,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> FailureAnalytics:
        """Retrieves failure error codes and retryable metrics."""
        s, e = cls._parse_and_validate_dates(start_date, end_date)
        return get_failure_analytics(db, start_date=s, end_date=e)

    @classmethod
    def get_channels(
        cls,
        db: Session,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> List[ChannelAnalytics]:
        """Retrieves per-channel dispatch performance metrics."""
        s, e = cls._parse_and_validate_dates(start_date, end_date)
        return get_channel_analytics(db, start_date=s, end_date=e)

    @classmethod
    def get_timeline(
        cls,
        db: Session,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> List[TimelinePoint]:
        """Retrieves daily time-series timeline aggregation."""
        s, e = cls._parse_and_validate_dates(start_date, end_date)
        return get_timeline_analytics(db, start_date=s, end_date=e)

    @classmethod
    def get_recent_activity(
        cls,
        db: Session,
        limit: int = 20,
    ) -> RecentActivityResponse:
        """Retrieves recent recovery activity stream."""
        items = get_recent_activity(db, limit=limit)
        return RecentActivityResponse(items=items, total=len(items))
