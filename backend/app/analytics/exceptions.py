"""
Analytics domain exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class AnalyticsError(AppException):
    """Base exception for analytics operations."""

    def __init__(
        self,
        message: str = "An analytics error occurred",
        status_code: int = 400,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class InvalidDateRangeError(AnalyticsError):
    """Raised when start_date is greater than end_date or format is invalid."""

    def __init__(
        self,
        message: str = "Invalid date range: start_date must be less than or equal to end_date",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=422, details=details)
