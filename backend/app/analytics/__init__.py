"""
RecoverAI Analytics Package.

Exposes AnalyticsService, schemas, and metrics calculation helpers.
"""

from app.analytics.exceptions import AnalyticsError, InvalidDateRangeError
from app.analytics.metrics import safe_average, safe_division
from app.analytics.schemas import (
    ApprovalAnalytics,
    ChannelAnalytics,
    ErrorBreakdownItem,
    ExecutionAnalytics,
    FailureAnalytics,
    OverviewMetrics,
    RecentActivityItem,
    RecentActivityResponse,
    RevenueAnalytics,
    TimelinePoint,
)
from app.analytics.service import AnalyticsService

__all__ = [
    "AnalyticsError",
    "InvalidDateRangeError",
    "AnalyticsService",
    "OverviewMetrics",
    "RevenueAnalytics",
    "ChannelAnalytics",
    "ExecutionAnalytics",
    "ApprovalAnalytics",
    "FailureAnalytics",
    "ErrorBreakdownItem",
    "TimelinePoint",
    "RecentActivityItem",
    "RecentActivityResponse",
    "safe_division",
    "safe_average",
]
