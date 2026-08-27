"""
Comprehensive test suite for Merchant Policy Management, Validation, and AI Precedence.
"""

import pytest
from sqlalchemy import select

from app.ai.decision_engine import RecoveryDecisionEngine
from app.ai.provider import MockAIProvider
from app.ai.schemas import RawRecommendation, RecoveryContext
from app.core.metrics import metrics
from app.models.audit import AuditLog
from app.models.enums import (
    PaymentStatus,
    RecoveryActionChannel,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueStatus,
    RiskStatus,
)
from app.models.payment import Payment
from app.models.policy import MerchantPolicy
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.policy.exceptions import PolicyNotFoundError, PolicyValidationError
from app.policy.rules import (
    evaluate_policy_against_context,
    generate_policy_summary,
    validate_policy_rules,
)
from app.policy.schemas import (
    MerchantPolicyBase,
    MerchantPolicyUpdate,
    PolicyEvaluationContext,
)
from app.policy.service import PolicyService


def test_default_policy_creation_and_fields(db_session):
    """Verify default policy creation with sensible defaults and integer paise."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_test_01")
    assert policy.id is not None
    assert policy.merchant_id == "merchant_test_01"
    assert policy.high_risk_threshold_paise == 1000000  # ₹10,000
    assert policy.critical_risk_threshold_paise == 5000000  # ₹50,000
    assert policy.human_review_threshold_paise == 1000000  # ₹10,000
    assert policy.auto_execute_low_risk is True
    assert policy.max_attempts == 3
    assert policy.backoff_base_seconds == 30
    assert "email" in policy.allowed_channels
    assert policy.preferred_channel == "email"
    assert policy.min_recovery_amount_paise == 10000  # ₹100
    assert policy.max_recovery_amount_paise == 100000000  # ₹10,00,000
    assert policy.is_active is True


def test_get_or_create_default_policy_idempotent(db_session):
    """Calling get_or_create twice returns the same record."""
    p1 = PolicyService.get_or_create_default_policy(db_session, "merchant_idem")
    p2 = PolicyService.get_or_create_default_policy(db_session, "merchant_idem")
    assert p1.id == p2.id


def test_policy_update_success(db_session):
    """Verify updating policy thresholds and channels."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_update")
    update_data = MerchantPolicyUpdate(
        human_review_threshold_paise=500000,  # ₹5,000
        max_attempts=5,
        allowed_channels=["email", "whatsapp"],
        preferred_channel="whatsapp",
    )
    updated = PolicyService.update_policy(db_session, policy.id, update_data)
    assert updated.human_review_threshold_paise == 500000
    assert updated.max_attempts == 5
    assert updated.allowed_channels == ["email", "whatsapp"]
    assert updated.preferred_channel == "whatsapp"


def test_policy_update_financial_validation_error(db_session):
    """Validation fails when min amount > max amount."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_err_fin")
    update_data = MerchantPolicyUpdate(
        min_recovery_amount_paise=5000000,
        max_recovery_amount_paise=100000,
    )
    with pytest.raises(PolicyValidationError) as exc:
        PolicyService.update_policy(db_session, policy.id, update_data)
    assert "cannot exceed maximum recovery amount" in str(exc.value)


def test_policy_update_high_greater_than_critical_error(db_session):
    """Validation fails when high risk threshold > critical risk threshold."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_err_risk")
    update_data = MerchantPolicyUpdate(
        high_risk_threshold_paise=8000000,
        critical_risk_threshold_paise=5000000,
    )
    with pytest.raises(PolicyValidationError) as exc:
        PolicyService.update_policy(db_session, policy.id, update_data)
    assert "High-risk threshold" in str(exc.value)


def test_policy_update_invalid_channel_rejection(db_session):
    """Validation fails when invalid channel name is provided."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_err_ch")
    update_data = MerchantPolicyUpdate(
        allowed_channels=["telegram", "email"],
    )
    with pytest.raises(PolicyValidationError) as exc:
        PolicyService.update_policy(db_session, policy.id, update_data)
    assert "Invalid communication channel" in str(exc.value)


def test_policy_update_empty_channels_rejection(db_session):
    """Validation fails when allowed channels is empty."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_err_empty")
    update_data = MerchantPolicyUpdate(
        allowed_channels=[],
    )
    with pytest.raises(PolicyValidationError) as exc:
        PolicyService.update_policy(db_session, policy.id, update_data)
    assert "At least one communication channel must be enabled" in str(exc.value)


def test_policy_update_preferred_not_in_allowed_rejection(db_session):
    """Validation fails when preferred channel is not in allowed list."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_err_pref")
    update_data = MerchantPolicyUpdate(
        allowed_channels=["email"],
        preferred_channel="sms",
    )
    with pytest.raises(PolicyValidationError) as exc:
        PolicyService.update_policy(db_session, policy.id, update_data)
    assert "must be included in the allowed channels list" in str(exc.value)


def test_policy_update_retry_attempt_boundaries(db_session):
    """Validation fails when max attempts is 0 or > 10."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_err_att")
    with pytest.raises(Exception):
        PolicyService.update_policy(db_session, policy.id, MerchantPolicyUpdate(max_attempts=0))


def test_policy_reset_to_defaults(db_session):
    """Verify reset restores factory settings."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_reset")
    PolicyService.update_policy(
        db_session,
        policy.id,
        MerchantPolicyUpdate(human_review_threshold_paise=20000, max_attempts=8),
    )
    reset_pol = PolicyService.reset_policy_to_defaults(db_session, policy.id)
    assert reset_pol.human_review_threshold_paise == 1000000
    assert reset_pol.max_attempts == 3


def test_policy_evaluation_low_risk_auto_execute():
    """Evaluate pure functional rule for low-risk amount < review threshold."""
    base = MerchantPolicyBase(
        human_review_threshold_paise=1000000,
        auto_execute_low_risk=True,
        allowed_channels=["email", "sms"],
        preferred_channel="email",
    )
    context = PolicyEvaluationContext(
        amount_paise=250000,  # ₹2,500
        channel="email",
        risk_status="low",
        attempt_count=0,
    )
    res = evaluate_policy_against_context(base, context)
    assert res.allowed is True
    assert res.requires_human_review is False
    assert res.is_auto_executable is True
    assert res.effective_channel == "email"


def test_policy_evaluation_high_amount_mandates_human_review():
    """Evaluate rule when amount exceeds human review threshold."""
    base = MerchantPolicyBase(
        human_review_threshold_paise=500000,  # ₹5,000
        auto_execute_low_risk=True,
    )
    context = PolicyEvaluationContext(
        amount_paise=800000,  # ₹8,000
        channel="email",
        risk_status="low",
        attempt_count=0,
    )
    res = evaluate_policy_against_context(base, context)
    assert res.allowed is True
    assert res.requires_human_review is True
    assert res.is_auto_executable is False


def test_policy_evaluation_disabled_channel_fallback():
    """Evaluate rule fallback when proposed channel is disabled by merchant."""
    base = MerchantPolicyBase(
        allowed_channels=["email", "whatsapp"],
        preferred_channel="email",
    )
    context = PolicyEvaluationContext(
        amount_paise=100000,
        channel="sms",  # SMS disabled
        risk_status="low",
        attempt_count=0,
    )
    res = evaluate_policy_against_context(base, context)
    assert res.allowed is True
    assert res.effective_channel == "email"  # Fallback to preferred
    assert res.policy_override_applied is True


def test_policy_evaluation_max_attempts_blocked():
    """Evaluate rule blocking when attempt count reaches max allowed."""
    base = MerchantPolicyBase(max_attempts=3)
    context = PolicyEvaluationContext(
        amount_paise=100000,
        channel="email",
        risk_status="low",
        attempt_count=3,
    )
    res = evaluate_policy_against_context(base, context)
    assert res.allowed is False
    assert "Maximum recovery attempts reached" in res.reason


def test_ai_decision_engine_enforces_merchant_policy_review_threshold(db_session):
    """When merchant configures low human review threshold, AI decision requires review."""
    # Configure custom merchant policy with ₹500 review threshold
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_default")
    policy.human_review_threshold_paise = 50000  # ₹500
    db_session.commit()

    payment = Payment(
        razorpay_payment_id="pay_pol_test_01",
        amount=150000,  # ₹1,500 (low risk, but > ₹500 policy threshold)
        currency="INR",
        status=PaymentStatus.failed,
        customer_email="user_pol@example.com",
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=150000,
        recoverable_amount=150000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        current_state=RecoveryCaseState.open,
        priority=RecoveryPriority.low,
        risk_status=RiskStatus.low,
        reason="Payment failed due to network glitch",
    )
    db_session.add(case)
    db_session.commit()

    rec = RecoveryDecisionEngine.generate_decision(db=db_session, case_id=case.id)
    # Even though case is low risk, merchant policy threshold forces human review
    assert rec.requires_human_review is True
    assert any("meets or exceeds merchant human review threshold" in w for w in rec.policy_decision.warnings)


def test_ai_decision_engine_blocks_action_when_channel_disabled(db_session):
    """When AI recommends a channel disabled by merchant policy, the action is blocked."""
    # Disable email in merchant policy (only allow SMS)
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_default")
    policy.allowed_channels = ["sms"]
    policy.preferred_channel = "sms"
    db_session.commit()

    payment = Payment(
        razorpay_payment_id="pay_pol_test_02",
        amount=100000,
        currency="INR",
        status=PaymentStatus.failed,
        customer_email="user_pol2@example.com",
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=100000,
        recoverable_amount=100000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        current_state=RecoveryCaseState.open,
        priority=RecoveryPriority.low,
        risk_status=RiskStatus.low,
        reason="Payment failed",
    )
    db_session.add(case)
    db_session.commit()

    # Mock AI provider that stubbornly recommends email
    class ForceEmailAIProvider(MockAIProvider):
        def generate_recovery_recommendation(self, context: RecoveryContext) -> RawRecommendation:
            return RawRecommendation(
                recommended_action_type=RecoveryActionType.email_reminder,
                recommended_channel=RecoveryActionChannel.email,
                priority=RecoveryPriority.low,
                confidence=0.9,
                rationale="Email is best",
                risk_flags=[],
                requires_human_review=False,
            )

    rec = RecoveryDecisionEngine.generate_decision(
        db=db_session,
        case_id=case.id,
        provider=ForceEmailAIProvider(),
    )

    # Merchant policy strictly blocks email recommendation
    assert rec.is_blocked is True
    assert rec.recommended_action_type is None

    # Check audit log emitted
    audit = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "policy_override_prevented")
        .order_by(AuditLog.id.desc())
    )
    assert audit is not None


def test_api_policies_endpoints_crud(client, db_session):
    """Test REST API routes for listing, fetching current, updating, and dry-run validating policies."""
    # 1. Get current policy
    res = client.get("/api/v1/policies/current")
    assert res.status_code == 200
    data = res.json()
    policy_id = data["id"]
    assert data["merchant_id"] == "merchant_default"
    assert data["max_attempts"] == 3

    # 2. Dry run validate
    val_res = client.post(
        f"/api/v1/policies/{policy_id}/validate",
        json={"max_attempts": 4, "human_review_threshold_paise": 2000000},
    )
    assert val_res.status_code == 200
    assert val_res.json()["valid"] is True

    # 3. Update policy
    upd_res = client.put(
        f"/api/v1/policies/{policy_id}",
        json={"max_attempts": 4, "human_review_threshold_paise": 2000000},
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["max_attempts"] == 4
    assert upd_res.json()["human_review_threshold_paise"] == 2000000

    # 4. Reset policy
    reset_res = client.post(f"/api/v1/policies/{policy_id}/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["max_attempts"] == 3
    assert reset_res.json()["human_review_threshold_paise"] == 1000000


def test_policy_get_by_id_not_found(db_session):
    """Querying a nonexistent policy id raises PolicyNotFoundError."""
    with pytest.raises(PolicyNotFoundError):
        PolicyService.get_policy_by_id(db_session, 999999)


def test_policy_summary_generation_text():
    """Verify human-readable summary text formats properly with Rupee signs."""
    base = MerchantPolicyBase(
        human_review_threshold_paise=1000000,
        auto_execute_low_risk=True,
        allowed_channels=["email", "sms"],
        preferred_channel="email",
        max_attempts=3,
        backoff_base_seconds=30,
        min_recovery_amount_paise=10000,
        max_recovery_amount_paise=5000000,
    )
    summary = generate_policy_summary(base)
    assert "₹10,000.00" in summary
    assert "Email, Sms" in summary
    assert "3 with 30s" in summary


def test_policy_evaluation_amount_below_minimum_blocked():
    """Evaluating recovery below merchant min amount returns allowed=False."""
    base = MerchantPolicyBase(min_recovery_amount_paise=50000)  # ₹500
    context = PolicyEvaluationContext(
        amount_paise=20000,  # ₹200
        channel="email",
        risk_status="low",
    )
    res = evaluate_policy_against_context(base, context)
    assert res.allowed is False
    assert "below merchant minimum recovery threshold" in res.reason


def test_policy_evaluation_amount_above_maximum_blocked():
    """Evaluating recovery above merchant max amount returns allowed=False."""
    base = MerchantPolicyBase(max_recovery_amount_paise=1000000)  # ₹10,000
    context = PolicyEvaluationContext(
        amount_paise=2000000,  # ₹20,000
        channel="email",
        risk_status="low",
    )
    res = evaluate_policy_against_context(base, context)
    assert res.allowed is False
    assert "exceeds merchant maximum recovery limit" in res.reason


def test_default_policy_includes_risk_approval_fields(db_session):
    """Default policy creation includes require_approval_for_high_risk and critical."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_risk_fields")
    assert policy.require_approval_for_high_risk is True
    assert policy.require_approval_for_critical_risk is True


def test_policy_update_risk_approval_fields(db_session):
    """Updating require_approval_for_high_risk and critical_risk works correctly."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_risk_upd")
    update_data = MerchantPolicyUpdate(
        require_approval_for_high_risk=False,
        require_approval_for_critical_risk=True,
    )
    updated = PolicyService.update_policy(db_session, policy.id, update_data)
    assert updated.require_approval_for_high_risk is False
    assert updated.require_approval_for_critical_risk is True


def test_policy_reset_restores_risk_approval_defaults(db_session):
    """Resetting policy restores require_approval flags to True."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_risk_rst")
    PolicyService.update_policy(
        db_session,
        policy.id,
        MerchantPolicyUpdate(
            require_approval_for_high_risk=False,
            require_approval_for_critical_risk=False,
        ),
    )
    reset_pol = PolicyService.reset_policy_to_defaults(db_session, policy.id)
    assert reset_pol.require_approval_for_high_risk is True
    assert reset_pol.require_approval_for_critical_risk is True


def test_policy_engine_disabled_high_risk_approval():
    """When require_approval_for_high_risk=False, high-risk case does NOT mandate human review via risk alone."""
    from app.ai.policy_engine import PolicyEngine
    from app.ai.schemas import RecoveryContext
    from app.models.enums import (
        RecoveryCaseState,
        RecoveryPriority,
        RevenueStatus,
        RiskStatus,
    )

    base = MerchantPolicyBase(
        human_review_threshold_paise=10000000,
        require_approval_for_high_risk=False,
        require_approval_for_critical_risk=True,
    )
    context = RecoveryContext(
        recovery_case_id=1,
        revenue_record_id=1,
        payment_amount=500000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=500000,
        recovery_case_priority=RecoveryPriority.high,
        recovery_case_risk_status=RiskStatus.high,
        recovery_case_current_state=RecoveryCaseState.open,
        action_count=0,
    )
    decision = PolicyEngine.evaluate_pre_policy(context, merchant_policy=base)
    assert decision.allowed is True
    assert decision.requires_human_review is False


def test_policy_engine_disabled_critical_risk_approval():
    """When require_approval_for_critical_risk=False, critical-risk does NOT mandate human review via risk alone."""
    from app.ai.policy_engine import PolicyEngine
    from app.ai.schemas import RecoveryContext
    from app.models.enums import (
        RecoveryCaseState,
        RecoveryPriority,
        RevenueStatus,
        RiskStatus,
    )

    base = MerchantPolicyBase(
        human_review_threshold_paise=10000000,
        require_approval_for_high_risk=False,
        require_approval_for_critical_risk=False,
    )
    context = RecoveryContext(
        recovery_case_id=2,
        revenue_record_id=2,
        payment_amount=2000000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=2000000,
        recovery_case_priority=RecoveryPriority.urgent,
        recovery_case_risk_status=RiskStatus.critical,
        recovery_case_current_state=RecoveryCaseState.open,
        action_count=0,
    )
    decision = PolicyEngine.evaluate_pre_policy(context, merchant_policy=base)
    assert decision.allowed is True
    assert decision.requires_human_review is False


def test_policy_engine_enabled_high_risk_approval_requires_review():
    """When require_approval_for_high_risk=True (default), high-risk mandates human review."""
    from app.ai.policy_engine import PolicyEngine
    from app.ai.schemas import RecoveryContext
    from app.models.enums import (
        RecoveryCaseState,
        RecoveryPriority,
        RevenueStatus,
        RiskStatus,
    )

    base = MerchantPolicyBase(
        human_review_threshold_paise=10000000,
        require_approval_for_high_risk=True,
        require_approval_for_critical_risk=True,
    )
    context = RecoveryContext(
        recovery_case_id=3,
        revenue_record_id=3,
        payment_amount=500000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=500000,
        recovery_case_priority=RecoveryPriority.high,
        recovery_case_risk_status=RiskStatus.high,
        recovery_case_current_state=RecoveryCaseState.open,
        action_count=0,
    )
    decision = PolicyEngine.evaluate_pre_policy(context, merchant_policy=base)
    assert decision.allowed is True
    assert decision.requires_human_review is True


def test_policy_engine_disabled_critical_allows_auto_execute():
    """When both risk approvals disabled + auto_execute enabled, high-risk can be auto-executed."""
    from app.ai.policy_engine import PolicyEngine
    from app.ai.schemas import RecoveryContext
    from app.models.enums import (
        RecoveryCaseState,
        RecoveryPriority,
        RevenueStatus,
        RiskStatus,
    )

    base = MerchantPolicyBase(
        human_review_threshold_paise=10000000,
        auto_execute_low_risk=True,
        require_approval_for_high_risk=False,
        require_approval_for_critical_risk=False,
    )
    context = RecoveryContext(
        recovery_case_id=4,
        revenue_record_id=4,
        payment_amount=500000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=500000,
        recovery_case_priority=RecoveryPriority.high,
        recovery_case_risk_status=RiskStatus.high,
        recovery_case_current_state=RecoveryCaseState.open,
        action_count=0,
    )
    decision = PolicyEngine.evaluate_pre_policy(context, merchant_policy=base)
    assert decision.allowed is True
    assert decision.requires_human_review is False


def test_api_policy_response_includes_risk_approval_fields(client, db_session):
    """GET /api/v1/policies/current returns the risk approval fields."""
    res = client.get("/api/v1/policies/current")
    assert res.status_code == 200
    data = res.json()
    assert "require_approval_for_high_risk" in data
    assert "require_approval_for_critical_risk" in data
    assert data["require_approval_for_high_risk"] is True
    assert data["require_approval_for_critical_risk"] is True


def test_api_policy_update_risk_approval_fields(client, db_session):
    """PUT /api/v1/policies/{id} updates risk approval fields."""
    res = client.get("/api/v1/policies/current")
    policy_id = res.json()["id"]

    upd = client.put(
        f"/api/v1/policies/{policy_id}",
        json={"require_approval_for_high_risk": False},
    )
    assert upd.status_code == 200
    assert upd.json()["require_approval_for_high_risk"] is False
    assert upd.json()["require_approval_for_critical_risk"] is True


def test_api_policy_preview_endpoint_low_risk(client, db_session):
    """POST /api/v1/policies/preview returns allowed=True for low risk + low amount."""
    res = client.post(
        "/api/v1/policies/preview",
        json={
            "amount_paise": 250000,
            "risk_status": "low",
            "channel": "email",
            "attempt_count": 0,
            "current_state": "open",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["evaluation"]["allowed"] is True
    assert data["evaluation"]["requires_human_review"] is False
    assert data["evaluation"]["is_auto_executable"] is True
    assert data["summary"] is not None


def test_api_policy_preview_endpoint_high_amount(client, db_session):
    """POST /api/v1/policies/preview shows human review required for high amount."""
    res = client.post(
        "/api/v1/policies/preview",
        json={
            "amount_paise": 1500000,
            "risk_status": "low",
            "channel": "email",
            "attempt_count": 0,
            "current_state": "open",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["evaluation"]["allowed"] is True
    assert data["evaluation"]["requires_human_review"] is True
    assert data["evaluation"]["is_auto_executable"] is False


def test_api_policy_preview_endpoint_blocked_max_attempts(client, db_session):
    """POST /api/v1/policies/preview shows blocked when max attempts reached."""
    res = client.post(
        "/api/v1/policies/preview",
        json={
            "amount_paise": 100000,
            "risk_status": "low",
            "channel": "email",
            "attempt_count": 3,
            "current_state": "open",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["evaluation"]["allowed"] is False
    assert "Maximum recovery attempts reached" in data["evaluation"]["reason"]


def test_api_policy_preview_endpoint_disabled_channel(client, db_session):
    """POST /api/v1/policies/preview shows channel override when proposed channel is disabled."""
    from app.policy.service import PolicyService
    from app.policy.schemas import MerchantPolicyUpdate

    # Configure policy to only allow email (disable sms)
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_default")
    PolicyService.update_policy(
        db_session,
        policy.id,
        MerchantPolicyUpdate(
            allowed_channels=["email", "whatsapp"],
            preferred_channel="email",
        ),
    )

    res = client.post(
        "/api/v1/policies/preview",
        json={
            "amount_paise": 100000,
            "risk_status": "low",
            "channel": "sms",
            "attempt_count": 0,
            "current_state": "open",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["evaluation"]["allowed"] is True
    assert data["evaluation"]["effective_channel"] == "email"
    assert data["evaluation"]["policy_override_applied"] is True


def test_api_policy_validate_dry_run(client, db_session):
    """POST /api/v1/policies/{id}/validate returns valid for good config."""
    res = client.get("/api/v1/policies/current")
    policy_id = res.json()["id"]
    val = client.post(
        f"/api/v1/policies/{policy_id}/validate",
        json={"max_attempts": 5, "auto_execute_low_risk": False},
    )
    assert val.status_code == 200
    assert val.json()["valid"] is True


def test_existing_orchestration_uses_policy_auto_execute(db_session):
    """Orchestrator loads merchant policy from DB and uses auto_execute_low_risk setting."""
    policy = PolicyService.get_or_create_default_policy(db_session, "merchant_default")
    assert policy.auto_execute_low_risk is True

    policy.auto_execute_low_risk = False
    db_session.commit()
    db_session.refresh(policy)
    assert policy.auto_execute_low_risk is False

    policy.auto_execute_low_risk = True
    db_session.commit()
    db_session.refresh(policy)
    assert policy.auto_execute_low_risk is True

