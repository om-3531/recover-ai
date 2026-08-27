"""
Day 11 Tests: Production Readiness, Provider Validation, Observability, Metrics & Hardening.

All tests run completely offline without real external network requests or paid credentials.
"""

import pytest

from app.core.config import Settings, get_settings
from app.core.metrics import metrics
from app.models.enums import (
    ApprovalStatus,
    PaymentStatus,
    RecoveryActionChannel,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueStatus,
    RiskStatus,
)
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.orchestration.orchestrator import RecoveryOrchestrator
from app.providers.base import ProviderContext
from app.providers.email import MockEmailProvider, SendGridEmailProvider
from app.providers.sms import MockSMSProvider, TwilioSMSProvider
from app.providers.validation import ProviderConfigurationService
from app.providers.webhook import HTTPWebhookProvider, MockWebhookProvider, is_safe_webhook_url
from app.providers.whatsapp import MetaWhatsAppProvider, MockWhatsAppProvider


@pytest.fixture(autouse=True)
def reset_test_metrics():
    """Ensure test metrics counters are reset between test runs."""
    metrics.reset()
    yield
    metrics.reset()


# --- 1. Configuration & Secret Sanitization ---


def test_configuration_defaults():
    """Verify application configuration defaults are secure and non-crashing."""
    settings = get_settings()
    assert settings.APP_NAME == "recover-ai-backend"
    assert settings.ENVIRONMENT in ("development", "staging", "production")
    assert settings.DEMO_MODE is True
    assert settings.JOB_MAX_ATTEMPTS == 3
    assert settings.WEBHOOK_TIMEOUT_SECONDS == 10.0


def test_missing_provider_configuration_detection(monkeypatch):
    """Verify that unconfigured providers accurately report missing fields without raising exceptions."""
    monkeypatch.setenv("SENDGRID_API_KEY", "")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "")

    status = ProviderConfigurationService.validate_sendgrid()
    assert status.configured is False
    assert status.enabled is False
    assert "SENDGRID_API_KEY" in status.missing_fields


def test_secret_sanitization_in_provider_status():
    """Verify that provider validation status never returns secret values."""
    status = ProviderConfigurationService.validate_twilio()
    dumped = status.model_dump()
    assert "auth_token" not in dumped
    assert "account_sid" not in dumped
    assert "password" not in dumped
    assert "api_key" not in dumped


# --- 2. System and Provider Status REST APIs ---


def test_get_system_status_endpoint(client):
    """Verify GET /api/v1/system/status returns safe operational details."""
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("operational", "degraded")
    assert data["service"] == "recover-ai-backend"
    assert "database" in data
    assert "job_queue_status" in data
    assert "providers_summary" in data
    assert "timestamp" in data
    assert "password" not in str(data).lower()
    assert "secret" not in str(data).lower()


def test_get_system_providers_endpoint(client):
    """Verify GET /api/v1/system/providers returns all provider readiness states."""
    response = client.get("/api/v1/system/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    provider_names = [p["provider"] for p in data["providers"]]
    assert "gemini" in provider_names
    assert "sendgrid" in provider_names
    assert "twilio" in provider_names
    assert "meta_whatsapp" in provider_names
    assert "http_webhook" in provider_names


def test_get_system_metrics_endpoint(client):
    """Verify GET /api/v1/system/metrics returns atomic telemetry counters."""
    metrics.increment("test_counter", 5)
    response = client.get("/api/v1/system/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert data["metrics"].get("test_counter") == 5


# --- 3. Request-ID Propagation and Structured Errors ---


def test_request_id_header_propagation(client):
    """Verify incoming X-Request-ID is preserved and propagated across responses."""
    custom_id = "test-req-correlation-id-12345"
    response = client.get("/api/v1/system/status", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_generated_request_id_when_omitted(client):
    """Verify X-Request-ID is automatically generated when not supplied by client."""
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") is not None
    assert len(response.headers.get("X-Request-ID")) > 10


# --- 4. Webhook Security & SSRF Protection ---


def test_webhook_url_validation_valid_https():
    """Verify valid public HTTPS URL passes security validation."""
    is_safe, reason = is_safe_webhook_url("https://api.partner.example.com/v1/recovery", allow_insecure_http=False)
    assert is_safe is True
    assert reason is None


def test_webhook_url_validation_blocks_http_in_production():
    """Verify insecure HTTP URL is rejected when insecure HTTP is disallowed."""
    is_safe, reason = is_safe_webhook_url("http://api.partner.example.com/v1/recovery", allow_insecure_http=False)
    assert is_safe is False
    assert "Insecure HTTP scheme is blocked" in reason


def test_webhook_url_validation_blocks_private_ips():
    """Verify private/loopback RFC1918 IPs are blocked for SSRF protection."""
    for ip in ["http://localhost:8000", "https://127.0.0.1:443", "https://10.0.0.1/ping", "https://192.168.1.1/hook"]:
        is_safe, reason = is_safe_webhook_url(ip, allow_insecure_http=False)
        assert is_safe is False
        assert "blocked for SSRF" in reason or "Insecure HTTP" in reason


def test_http_webhook_provider_dispatch_rejection():
    """Verify HTTPWebhookProvider rejects unsafe loopback target in production mode."""
    provider = HTTPWebhookProvider()
    context = ProviderContext(
        recovery_case_id=1,
        action_type=RecoveryActionType.webhook_ping,
        channel=RecoveryActionChannel.webhook,
        metadata={"webhook_url": "http://127.0.0.1:9999/hack"},
    )
    result = provider.send(context)
    assert result.success is False
    assert result.error_code in ("UNSAFE_WEBHOOK_URL", "MISSING_WEBHOOK_URL")


# --- 5. Provider Dispatch Error Classification ---


def test_mock_email_provider_retryable_timeout():
    """Verify MockEmailProvider timeout is classified as retryable."""
    provider = MockEmailProvider(force_failure=True, retryable_failure=True)
    context = ProviderContext(
        recovery_case_id=1,
        customer_email="customer@example.com",
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    result = provider.send(context)
    assert result.success is False
    assert result.retryable is True
    assert result.error_code == "EMAIL_GATEWAY_TIMEOUT"


def test_mock_sms_provider_permanent_invalid_number():
    """Verify MockSMSProvider invalid phone is classified as permanent failure."""
    provider = MockSMSProvider(force_failure=True, retryable_failure=False)
    context = ProviderContext(
        recovery_case_id=1,
        customer_phone="+910000000000",
        action_type=RecoveryActionType.sms_reminder,
        channel=RecoveryActionChannel.sms,
    )
    result = provider.send(context)
    assert result.success is False
    assert result.retryable is False
    assert result.error_code == "INVALID_PHONE_NUMBER"


def test_unconfigured_sendgrid_returns_safe_failure():
    """Verify unconfigured SendGrid provider returns structured error without throwing."""
    provider = SendGridEmailProvider(api_key="")
    context = ProviderContext(
        recovery_case_id=1,
        customer_email="customer@example.com",
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
    )
    result = provider.send(context)
    assert result.success is False
    assert result.error_code == "PROVIDER_NOT_CONFIGURED"


def test_unconfigured_twilio_returns_safe_failure():
    """Verify unconfigured Twilio provider returns structured error without throwing."""
    provider = TwilioSMSProvider(account_sid="", auth_token="")
    context = ProviderContext(
        recovery_case_id=1,
        customer_phone="+919876543210",
        action_type=RecoveryActionType.sms_reminder,
        channel=RecoveryActionChannel.sms,
    )
    result = provider.send(context)
    assert result.success is False
    assert result.error_code == "PROVIDER_NOT_CONFIGURED"


def test_unconfigured_whatsapp_returns_safe_failure():
    """Verify unconfigured Meta WhatsApp provider returns structured error without throwing."""
    provider = MetaWhatsAppProvider(access_token="", phone_number_id="")
    context = ProviderContext(
        recovery_case_id=1,
        customer_phone="+919876543210",
        action_type=RecoveryActionType.whatsapp_reminder,
        channel=RecoveryActionChannel.whatsapp,
    )
    result = provider.send(context)
    assert result.success is False
    assert result.error_code == "PROVIDER_NOT_CONFIGURED"


# --- 6. Metrics Telemetry Tracking ---


def test_metrics_counter_increments_during_orchestration(db_session):
    """Verify metrics counters increment atomically when orchestration runs."""
    payment = Payment(
        razorpay_payment_id="pay_metric_01",
        amount=250000,
        currency="INR",
        status=PaymentStatus.failed,
        customer_email="metric_user@example.com",
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=250000,
        recoverable_amount=250000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )

    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        current_state=RecoveryCaseState.open,
        priority=RecoveryPriority.medium,
        risk_status=RiskStatus.low,
        reason="Payment failed on Razorpay checkout",
    )

    db_session.add(case)
    db_session.commit()

    initial_completions = metrics.get_count("orchestration_completions_total")

    # Orchestrate recovery
    res = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=case.id,
        auto_execute_low_risk=True,
    )
    assert res.status.value == "completed"

    # Verify metrics incremented
    assert metrics.get_count("orchestration_completions_total") == initial_completions + 1
    assert metrics.get_count("ai_decisions_total") >= 1
    assert metrics.get_count("approvals_total") >= 1
    assert metrics.get_count("execution_successes_total") >= 1


# --- 7. Health and Readiness Hardening ---


def test_liveness_health_endpoint(client):
    """Verify /health is ultra-lightweight and returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "recover-ai-backend"}


def test_readiness_probe_with_db(client):
    """Verify /ready verifies DB connectivity returning 200 OK without leaking secrets."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "password" not in str(data).lower()
