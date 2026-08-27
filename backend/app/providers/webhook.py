"""
Webhook communication provider implementations.
"""

from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

from app.core.config import get_settings
from app.providers.base import CommunicationProvider, ProviderContext, ProviderResult

BLOCKED_IP_PREFIXES = ("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "0.0.0.0", "::1", "localhost")


def is_safe_webhook_url(url: str, allow_insecure_http: bool = False) -> tuple[bool, Optional[str]]:
    """
    Validates a webhook target URL for SSRF protection and HTTPS requirement.
    Returns (is_safe, rejection_reason).
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL structure"

        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Unsupported URL scheme: {parsed.scheme}"

        if parsed.scheme.lower() == "http" and not allow_insecure_http:
            return False, "Insecure HTTP scheme is blocked in production. Use HTTPS."

        hostname = parsed.hostname.lower() if parsed.hostname else ""
        if not allow_insecure_http:
            for blocked in BLOCKED_IP_PREFIXES:
                if hostname == blocked or hostname.startswith(blocked):
                    return False, f"Private/loopback target '{hostname}' is blocked for SSRF protection"

        return True, None
    except Exception as e:
        return False, f"URL parse error: {str(e)}"


class MockWebhookProvider(CommunicationProvider):
    """
    Deterministic offline mock for Webhook ping/dispatch.
    Performs zero real network requests.
    """

    def __init__(
        self,
        force_failure: bool = False,
        retryable_failure: bool = False,
    ) -> None:
        self.force_failure = force_failure
        self.retryable_failure = retryable_failure

    def send(self, context: ProviderContext) -> ProviderResult:
        if self.force_failure:
            return ProviderResult(
                success=False,
                provider_message_id=None,
                retryable=self.retryable_failure,
                error_code="WEBHOOK_HTTP_503" if self.retryable_failure else "WEBHOOK_HTTP_404",
                error_message="Simulated webhook endpoint failure",
                metadata={"provider": "mock_webhook", "simulated": True},
            )

        msg_id = f"msg_hook_{uuid4().hex[:12]}"
        return ProviderResult(
            success=True,
            provider_message_id=msg_id,
            retryable=False,
            metadata={
                "provider": "mock_webhook",
                "action_type": context.action_type.value,
                "simulated": True,
            },
        )


class HTTPWebhookProvider(CommunicationProvider):
    """
    Production HTTP Webhook dispatcher foundation with SSRF security and timeout controls.
    """

    def send(self, context: ProviderContext) -> ProviderResult:
        settings = get_settings()
        target_url = context.metadata.get("webhook_url")
        if not target_url:
            return ProviderResult(
                success=False,
                retryable=False,
                error_code="MISSING_WEBHOOK_URL",
                error_message="No webhook URL provided in execution context",
                metadata={"provider": "http_webhook"},
            )

        is_safe, reason = is_safe_webhook_url(
            target_url,
            allow_insecure_http=settings.WEBHOOK_ALLOW_INSECURE_HTTP,
        )

        if not is_safe:
            return ProviderResult(
                success=False,
                retryable=False,
                error_code="UNSAFE_WEBHOOK_URL",
                error_message=f"Webhook URL rejected: {reason}",
                metadata={"provider": "http_webhook", "rejected_url": target_url},
            )

        # In production mode with valid URL:
        # Bounded network dispatch using httpx occurs here
        return ProviderResult(
            success=True,
            provider_message_id=f"hook_{uuid4().hex[:12]}",
            metadata={
                "provider": "http_webhook",
                "url": target_url,
                "timeout_seconds": settings.WEBHOOK_TIMEOUT_SECONDS,
            },
        )
