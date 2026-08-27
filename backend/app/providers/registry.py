"""
Communication Provider Registry.

Resolves the appropriate CommunicationProvider for a given RecoveryActionChannel.
Defaults to safe, deterministic mock providers for 100% offline local development and test execution.
"""

from typing import Optional

from app.models.enums import RecoveryActionChannel
from app.providers.base import CommunicationProvider
from app.providers.email import MockEmailProvider
from app.providers.exceptions import ProviderConfigurationError
from app.providers.sms import MockSMSProvider
from app.providers.webhook import MockWebhookProvider
from app.providers.whatsapp import MockWhatsAppProvider


class ProviderRegistry:
    """Registry mapping recovery channels to communication provider adapters."""

    def __init__(self) -> None:
        self._providers: dict[RecoveryActionChannel, CommunicationProvider] = {
            RecoveryActionChannel.email: MockEmailProvider(),
            RecoveryActionChannel.sms: MockSMSProvider(),
            RecoveryActionChannel.whatsapp: MockWhatsAppProvider(),
            RecoveryActionChannel.webhook: MockWebhookProvider(),
            RecoveryActionChannel.in_app: MockWebhookProvider(),
            RecoveryActionChannel.system: MockWebhookProvider(),
        }

    def register(
        self,
        channel: RecoveryActionChannel,
        provider: CommunicationProvider,
    ) -> None:
        """Register or override a provider implementation for a channel."""
        self._providers[channel] = provider

    def get_provider(
        self,
        channel: RecoveryActionChannel,
    ) -> CommunicationProvider:
        """Resolve the provider registered for a channel."""
        provider = self._providers.get(channel)
        if provider is None:
            raise ProviderConfigurationError(
                f"No provider registered for channel '{channel.value}'"
            )
        return provider


# Default shared registry instance
_default_registry = ProviderRegistry()


def get_default_provider_registry() -> ProviderRegistry:
    """Return the global default provider registry."""
    return _default_registry
