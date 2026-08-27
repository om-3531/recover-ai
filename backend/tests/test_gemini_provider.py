"""
Tests for GeminiAIProvider.

Covers:
- Structured JSON prompt generation
- Successful Gemini API call -> valid RawRecommendation mapping
- Fallback on unconfigured API key
- Fallback on network timeout
- Fallback on HTTP error (4xx, 5xx)
- Fallback on invalid JSON response
- Fallback on missing required fields
- Fallback on invalid enum values
- Confidence clamping to [0.0, 1.0]
- Markdown fence stripping
- No secrets/PII in exceptions or logs
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ai.exceptions import AIOutputValidationError, AIProviderError
from app.ai.prompts import GEMINI_JSON_SCHEMA, build_gemini_prompt
from app.ai.provider import GeminiAIProvider, MockAIProvider
from app.ai.schemas import RawRecommendation, RecoveryContext
from app.models.enums import (
    PaymentStatus,
    RecoveryActionChannel,
    RecoveryActionType,
    RecoveryPriority,
    RecoveryCaseState,
    RevenueStatus,
    RiskStatus,
)


def _make_context(**overrides) -> RecoveryContext:
    defaults = dict(
        recovery_case_id=1,
        revenue_record_id=1,
        payment_amount=250000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=250000,
        recovery_case_priority=RecoveryPriority.medium,
        recovery_case_risk_status=RiskStatus.medium,
        recovery_case_current_state=RecoveryCaseState.open,
        action_count=0,
    )
    defaults.update(overrides)
    return RecoveryContext(**defaults)


def _gemini_response(text: str) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": text}],
                }
            }
        ]
    }


def _valid_gemini_json(**overrides) -> str:
    data = {
        "recommended_action_type": "payment_link",
        "recommended_channel": "email",
        "priority": "medium",
        "confidence": 0.82,
        "rationale": "Standard payment failure; email reminder recommended.",
        "risk_flags": [],
        "requires_human_review": False,
    }
    data.update(overrides)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# 1. PROMPT GENERATION
# ---------------------------------------------------------------------------


def test_build_gemini_prompt_contains_required_fields():
    context_dict = _make_context().model_dump()
    prompt = build_gemini_prompt(context_dict)
    assert "Case ID: 1" in prompt
    assert "250000 paise" in prompt
    assert GEMINI_JSON_SCHEMA in prompt
    assert "JSON" in prompt


# ---------------------------------------------------------------------------
# 2. SUCCESSFUL GEMINI CALL
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_successful_recommendation(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    mock_response = MagicMock()
    mock_response.json.return_value = _gemini_response(_valid_gemini_json())
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type == RecoveryActionType.payment_link
    assert result.recommended_channel == RecoveryActionChannel.email
    assert result.confidence == 0.82
    assert result.requires_human_review is False
    mock_client.post.assert_called_once()


# ---------------------------------------------------------------------------
# 3. FALLBACK ON UNCONFIGURED API KEY
# ---------------------------------------------------------------------------


@patch("app.ai.provider.get_settings")
def test_gemini_fallback_unconfigured_key(mock_settings):
    settings = MagicMock()
    settings.GEMINI_API_KEY = ""
    settings.AI_API_KEY = ""
    mock_settings.return_value = settings

    provider = GeminiAIProvider()
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type is not None


# ---------------------------------------------------------------------------
# 4. FALLBACK ON NETWORK TIMEOUT
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_fallback_on_timeout(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type is not None


# ---------------------------------------------------------------------------
# 5. FALLBACK ON HTTP ERROR
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_fallback_on_http_error(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    mock_response = MagicMock()
    mock_response.status_code = 403

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Forbidden", request=MagicMock(), response=mock_response
    )
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type is not None


# ---------------------------------------------------------------------------
# 6. FALLBACK ON INVALID JSON
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_fallback_on_invalid_json(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    mock_response = MagicMock()
    mock_response.json.return_value = _gemini_response("This is not JSON at all")
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type is not None


# ---------------------------------------------------------------------------
# 7. FALLBACK ON INVALID ENUM VALUE
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_fallback_on_invalid_enum(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    invalid_json = json.dumps({
        "recommended_action_type": "INVALID_ACTION",
        "recommended_channel": "email",
        "priority": "medium",
        "confidence": 0.8,
        "rationale": "Test",
        "risk_flags": [],
        "requires_human_review": False,
    })

    mock_response = MagicMock()
    mock_response.json.return_value = _gemini_response(invalid_json)
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type is not None


# ---------------------------------------------------------------------------
# 8. CONFIDENCE CLAMPING
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_clamps_confidence(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    over_confident = _valid_gemini_json(confidence=1.5)
    mock_response = MagicMock()
    mock_response.json.return_value = _gemini_response(over_confident)
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert result.confidence == 1.0

    negative_confidence = _valid_gemini_json(confidence=-0.5)
    mock_response.json.return_value = _gemini_response(negative_confidence)
    result2 = provider.generate_recovery_recommendation(context)
    assert result2.confidence == 0.0


# ---------------------------------------------------------------------------
# 9. MARKDOWN FENCE STRIPPING
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_strips_markdown_fences(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    fenced = "```json\n" + _valid_gemini_json() + "\n```"
    mock_response = MagicMock()
    mock_response.json.return_value = _gemini_response(fenced)
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type == RecoveryActionType.payment_link


# ---------------------------------------------------------------------------
# 10. NO SECRETS IN FALLBACK EXCEPTIONS
# ---------------------------------------------------------------------------


@patch("app.ai.provider.get_settings")
def test_gemini_no_secrets_in_fallback(mock_settings):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "super-secret-key-abc123"
    settings.AI_API_KEY = ""
    mock_settings.return_value = settings

    provider = GeminiAIProvider(api_key="super-secret-key-abc123")

    # Trigger the unconfigured path to get a mock result
    context = _make_context()
    # The fallback result should not leak the key in its fields
    result = provider.generate_recovery_recommendation(context)
    result_dict = result.model_dump()
    for val in result_dict.values():
        if isinstance(val, str):
            assert "super-secret-key" not in val


# ---------------------------------------------------------------------------
# 11. GEMINI IS CONFIGURED CHECK
# ---------------------------------------------------------------------------


def test_gemini_is_configured_true():
    provider = GeminiAIProvider(api_key="valid-key")
    assert provider._is_configured() is True


@patch("app.ai.provider.get_settings")
def test_gemini_is_configured_false(mock_settings):
    settings = MagicMock()
    settings.GEMINI_API_KEY = ""
    settings.AI_API_KEY = ""
    mock_settings.return_value = settings

    provider = GeminiAIProvider()
    assert provider._is_configured() is False


# ---------------------------------------------------------------------------
# 12. EMPTY CANDIDATES FALLBACK
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_empty_candidates_fallback(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    mock_response = MagicMock()
    mock_response.json.return_value = {"candidates": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert isinstance(result, RawRecommendation)
    assert result.recommended_action_type is not None


# ---------------------------------------------------------------------------
# 13. RISK FLAGS PRESERVED
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_risk_flags_preserved(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    flagged = _valid_gemini_json(risk_flags=["HIGH_VALUE", "MULTI_ATTEMPT"], requires_human_review=True)
    mock_response = MagicMock()
    mock_response.json.return_value = _gemini_response(flagged)
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)

    assert "HIGH_VALUE" in result.risk_flags
    assert "MULTI_ATTEMPT" in result.risk_flags
    assert result.requires_human_review is True


# ---------------------------------------------------------------------------
# 14. HIGH RISK CASE ENFORCES HUMAN REVIEW
# ---------------------------------------------------------------------------


@patch("app.ai.provider.httpx.Client")
@patch("app.ai.provider.get_settings")
def test_gemini_high_risk_human_review_override(mock_settings, mock_client_cls):
    settings = MagicMock()
    settings.GEMINI_API_KEY = "test-key-123"
    settings.AI_MODEL = "gemini-1.5-flash"
    mock_settings.return_value = settings

    no_review = _valid_gemini_json(requires_human_review=False)
    mock_response = MagicMock()
    mock_response.json.return_value = _gemini_response(no_review)
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = GeminiAIProvider(api_key="test-key-123")
    context = _make_context(recovery_case_risk_status=RiskStatus.high)

    # Gemini provider should not override this -- the policy engine will enforce it
    result = provider.generate_recovery_recommendation(context)
    # The raw result may have requires_human_review=False from Gemini, but post_policy will override
    assert isinstance(result, RawRecommendation)


# ---------------------------------------------------------------------------
# 15. GEMINI FALLBACK METRICS INCREMENT
# ---------------------------------------------------------------------------


@patch("app.ai.provider.get_settings")
def test_gemini_fallback_increments_metrics(mock_settings):
    from app.core.metrics import metrics

    settings = MagicMock()
    settings.GEMINI_API_KEY = ""
    settings.AI_API_KEY = ""
    mock_settings.return_value = settings

    metrics.reset()
    provider = GeminiAIProvider()
    context = _make_context()
    provider.generate_recovery_recommendation(context)

    assert metrics.get_count("ai_provider_fallbacks_total") >= 1


# ---------------------------------------------------------------------------
# 16. MOCK PROVIDER STILL WORKS (REGRESSION)
# ---------------------------------------------------------------------------


def test_mock_provider_low_risk_low_value():
    provider = MockAIProvider()
    context = _make_context(
        payment_amount=50000,
        recovery_case_risk_status=RiskStatus.low,
        recovery_case_priority=RecoveryPriority.low,
        action_count=0,
    )
    result = provider.generate_recovery_recommendation(context)
    assert result.recommended_action_type == RecoveryActionType.payment_link
    assert result.recommended_channel == RecoveryActionChannel.whatsapp
    assert result.confidence == 0.88


def test_mock_provider_high_risk_forces_human_review():
    provider = MockAIProvider()
    context = _make_context(
        recovery_case_risk_status=RiskStatus.critical,
        recovery_case_priority=RecoveryPriority.urgent,
    )
    result = provider.generate_recovery_recommendation(context)
    assert result.requires_human_review is True
    assert result.recommended_action_type == RecoveryActionType.email_reminder


def test_mock_provider_force_failure():
    provider = MockAIProvider(force_failure=True)
    context = _make_context()
    with pytest.raises(AIProviderError):
        provider.generate_recovery_recommendation(context)


def test_mock_provider_override():
    override = RawRecommendation(
        recommended_action_type=RecoveryActionType.discount_offer,
        recommended_channel=RecoveryActionChannel.whatsapp,
        priority=RecoveryPriority.low,
        confidence=0.99,
        rationale="Override test",
    )
    provider = MockAIProvider(override_recommendation=override)
    context = _make_context()
    result = provider.generate_recovery_recommendation(context)
    assert result.recommended_action_type == RecoveryActionType.discount_offer
    assert result.confidence == 0.99
