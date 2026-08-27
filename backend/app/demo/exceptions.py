"""
Demo domain exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class DemoError(AppException):
    """Base exception for demo operations."""

    def __init__(
        self,
        message: str = "A demo operation error occurred",
        status_code: int = 400,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class DemoModeDisabledError(DemoError):
    """Raised when demo operations are attempted in environments where DEMO_MODE is disabled."""

    def __init__(
        self,
        message: str = "Demo endpoints and seeding are disabled. Set DEMO_MODE=true in configuration to enable.",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=403, details=details)
