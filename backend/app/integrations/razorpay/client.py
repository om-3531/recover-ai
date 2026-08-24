"""
Razorpay HTTP Client.

Encapsulates external API communication with Razorpay using HTTP Basic Auth.
Does not log secrets or raw credentials.
"""

from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.integrations.razorpay.exceptions import (
    RazorpayConfigurationError,
    RazorpayOrderCreationError,
)


class RazorpayClient:
    """Client for interacting with Razorpay REST APIs."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        base_url: str = "https://api.razorpay.com/v1",
        timeout: float = 10.0,
    ) -> None:
        settings = get_settings()
        self.key_id = key_id if key_id is not None else settings.RAZORPAY_KEY_ID
        self.key_secret = (
            key_secret if key_secret is not None else settings.RAZORPAY_KEY_SECRET
        )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get_auth(self) -> tuple[str, str]:
        """Validate and return HTTP Basic Auth tuple."""
        if not self.key_id or not self.key_secret:
            raise RazorpayConfigurationError(
                "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be configured"
            )
        return (self.key_id, self.key_secret)

    def create_order(
        self,
        amount: int,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Create a new payment order in Razorpay.

        Amount must be an integer in paise (e.g. 50000 = 500.00 INR).
        """
        if amount <= 0:
            raise ValueError("Order amount must be greater than zero")

        auth = self._get_auth()
        payload: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
        }
        if receipt is not None:
            payload["receipt"] = receipt
        if notes is not None:
            payload["notes"] = notes

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/orders",
                    json=payload,
                    auth=auth,
                )
                if response.is_error:
                    error_data = (
                        response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    )
                    error_description = (
                        error_data.get("error", {}).get("description")
                        or f"HTTP {response.status_code}"
                    )
                    raise RazorpayOrderCreationError(
                        f"Razorpay order creation failed: {error_description}",
                        details=error_data.get("error"),
                    )
                return response.json()
        except httpx.RequestError as exc:
            raise RazorpayOrderCreationError(
                f"Network error connecting to Razorpay: {exc.__class__.__name__}"
            ) from exc
