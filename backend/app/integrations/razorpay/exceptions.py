"""
Razorpay integration exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class RazorpayIntegrationError(AppException):
    """Base exception for external Razorpay API integration failures."""

    def __init__(
        self,
        message: str = "Razorpay integration error",
        status_code: int = 502,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class RazorpaySignatureVerificationError(AppException):
    """Raised when a payment or webhook signature verification fails."""

    def __init__(
        self,
        message: str = "Invalid Razorpay signature",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)


class RazorpayOrderCreationError(RazorpayIntegrationError):
    """Raised when Razorpay order creation fails."""

    def __init__(
        self,
        message: str = "Failed to create Razorpay order",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=502, details=details)


class RazorpayConfigurationError(AppException):
    """Raised when required Razorpay credentials or settings are missing."""

    def __init__(
        self,
        message: str = "Razorpay configuration is missing or invalid",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=500, details=details)
