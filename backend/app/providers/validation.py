"""
Provider configuration validation service.

Verifies third-party provider readiness without ever leaking API keys, tokens, or credentials.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings


class ProviderConfigStatus(BaseModel):
    """Sanitized configuration readiness summary for an individual provider."""

    provider: str
    channel: str
    configured: bool
    enabled: bool
    safe_to_use: bool
    missing_fields: List[str]
    mode: str = "mock"  # "mock" or "real"

    model_config = ConfigDict(from_attributes=True)


class ProviderConfigurationService:
    """Service to validate and inspect provider readiness across AI and communication channels."""

    @classmethod
    def validate_gemini(cls) -> ProviderConfigStatus:
        settings = get_settings()
        missing = []
        api_key = getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "AI_API_KEY", "")
        if not api_key:
            missing.append("GEMINI_API_KEY")

        is_configured = len(missing) == 0
        is_enabled = settings.AI_PROVIDER.lower() == "gemini" and is_configured

        return ProviderConfigStatus(
            provider="gemini",
            channel="ai_engine",
            configured=is_configured,
            enabled=is_enabled,
            safe_to_use=True,
            missing_fields=missing,
            mode="real" if is_enabled else "mock",
        )

    @classmethod
    def validate_sendgrid(cls) -> ProviderConfigStatus:
        settings = get_settings()
        missing = []
        if not getattr(settings, "SENDGRID_API_KEY", ""):
            missing.append("SENDGRID_API_KEY")
        if not getattr(settings, "SENDGRID_FROM_EMAIL", ""):
            missing.append("SENDGRID_FROM_EMAIL")

        is_configured = len(missing) == 0
        return ProviderConfigStatus(
            provider="sendgrid",
            channel="email",
            configured=is_configured,
            enabled=is_configured,
            safe_to_use=True,
            missing_fields=missing,
            mode="real" if is_configured else "mock",
        )

    @classmethod
    def validate_twilio(cls) -> ProviderConfigStatus:
        settings = get_settings()
        missing = []
        if not getattr(settings, "TWILIO_ACCOUNT_SID", ""):
            missing.append("TWILIO_ACCOUNT_SID")
        if not getattr(settings, "TWILIO_AUTH_TOKEN", ""):
            missing.append("TWILIO_AUTH_TOKEN")
        if not getattr(settings, "TWILIO_FROM_NUMBER", ""):
            missing.append("TWILIO_FROM_NUMBER")

        is_configured = len(missing) == 0
        return ProviderConfigStatus(
            provider="twilio",
            channel="sms",
            configured=is_configured,
            enabled=is_configured,
            safe_to_use=True,
            missing_fields=missing,
            mode="real" if is_configured else "mock",
        )

    @classmethod
    def validate_whatsapp(cls) -> ProviderConfigStatus:
        settings = get_settings()
        missing = []
        token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or getattr(settings, "META_WHATSAPP_TOKEN", "")
        if not token:
            missing.append("WHATSAPP_ACCESS_TOKEN")
        if not getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", ""):
            missing.append("WHATSAPP_PHONE_NUMBER_ID")

        is_configured = len(missing) == 0
        return ProviderConfigStatus(
            provider="meta_whatsapp",
            channel="whatsapp",
            configured=is_configured,
            enabled=is_configured,
            safe_to_use=True,
            missing_fields=missing,
            mode="real" if is_configured else "mock",
        )

    @classmethod
    def validate_webhook(cls) -> ProviderConfigStatus:
        settings = get_settings()
        return ProviderConfigStatus(
            provider="http_webhook",
            channel="webhook",
            configured=True,
            enabled=True,
            safe_to_use=True,
            missing_fields=[],
            mode="production" if not settings.WEBHOOK_ALLOW_INSECURE_HTTP else "development",
        )

    @classmethod
    def get_all_provider_statuses(cls) -> List[ProviderConfigStatus]:
        """Returns the readiness status of all communication and AI providers."""
        return [
            cls.validate_gemini(),
            cls.validate_sendgrid(),
            cls.validate_twilio(),
            cls.validate_whatsapp(),
            cls.validate_webhook(),
        ]
