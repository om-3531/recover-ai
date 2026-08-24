"""
Tests for AI Recovery Decision Engine, Deterministic Policy Engine, and Provider Abstraction.

Covers:
- Sanitized context construction (paise amounts, no secrets/PII leaks)
- Deterministic policy enforcement (pre-policy and post-policy checks)
- Blocking terminal states (recovered, closed) and zero recoverable balances
- High and critical risk human review requirement enforcement
- Policy override of excessive automated retries (>= 3 attempts)
- Mock AI provider deterministic heuristics and error handling
- REST API endpoint: POST /api/v1/ai/recovery-cases/{case_id}/decision
- Non-destructive execution guarantee (AI cannot mutate payment/revenue/case state directly)
- Audit trail recording for all decision requests, blocks, and completions
"""

import pytest

from app.ai.decision_engine import RecoveryDecisionEngine
from app.ai.exceptions import AIProviderError
from app.ai.policy_engine import PolicyEngine
from app.ai.provider import MockAIProvider
from app.ai.schemas import RawRecommendation, RecoveryContext
from app.core.exceptions import NotFoundError
from app.models.enums import (
    PaymentMethod,
    PaymentStatus,
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueStatus,
    RiskStatus,
)
from app.models.payment import Payment
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord
from app.services.audit_service import AuditService


@pytest.fixture
def sample_case_setup(db_session):
    """Fixture that creates a realistic failed payment, revenue record, and recovery case."""
    payment = Payment(
        razorpay_payment_id="pay_ai_test_001",
        razorpay_order_id="order_ai_001",
        amount=250000,  # 2,500.00 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
        customer_email="payer@example.com",
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
        reason="card_declined_insufficient_funds",
        risk_status=RiskStatus.medium,
        priority=RecoveryPriority.medium,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    return case


# ---------------------------------------------------------------------------
# 1. CONTEXT CONSTRUCTION & SANITIZATION
# ---------------------------------------------------------------------------


def test_context_construction(db_session, sample_case_setup):
    """Test that RecoveryContext is correctly constructed with sanitized fields."""
    context = RecoveryDecisionEngine._build_context(db_session, sample_case_setup)

    assert context.recovery_case_id == sample_case_setup.id
    assert context.payment_amount == 250000
    assert context.recoverable_amount == 250000
    assert context.currency == "INR"
    assert context.payment_status == PaymentStatus.failed
    assert context.revenue_status == RevenueStatus.at_risk
    assert context.recovery_case_risk_status == RiskStatus.medium
    assert context.action_count == 0

    # Ensure no secrets or unnecessary PII fields exist on context
    context_dict = context.model_dump()
    assert "password" not in context_dict
    assert "key_secret" not in context_dict
    assert "webhook_secret" not in context_dict


# ---------------------------------------------------------------------------
# 2. DETERMINISTIC POLICY ENGINE TESTS
# ---------------------------------------------------------------------------


def test_policy_blocks_recovered_or_closed_case():
    """Policy must block decision generation for recovered or closed cases."""
    context_recovered = RecoveryContext(
        recovery_case_id=1,
        revenue_record_id=1,
        payment_amount=100000,
        currency="INR",
        payment_status=PaymentStatus.captured,
        revenue_status=RevenueStatus.recovered,
        recoverable_amount=0,
        recovery_case_priority=RecoveryPriority.low,
        recovery_case_risk_status=RiskStatus.low,
        recovery_case_current_state=RecoveryCaseState.recovered,
    )
    decision = PolicyEngine.evaluate_pre_policy(context_recovered)
    assert decision.allowed is False
    assert "recovered" in decision.reason.lower()

    context_closed = RecoveryContext(
        recovery_case_id=2,
        revenue_record_id=2,
        payment_amount=100000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.lost,
        recoverable_amount=100000,
        recovery_case_priority=RecoveryPriority.low,
        recovery_case_risk_status=RiskStatus.low,
        recovery_case_current_state=RecoveryCaseState.closed,
    )
    decision_closed = PolicyEngine.evaluate_pre_policy(context_closed)
    assert decision_closed.allowed is False
    assert "closed" in decision_closed.reason.lower()


def test_policy_blocks_zero_recoverable_amount():
    """Policy must block decision generation when recoverable amount is 0."""
    context_zero = RecoveryContext(
        recovery_case_id=3,
        revenue_record_id=3,
        payment_amount=100000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=0,
        recovery_case_priority=RecoveryPriority.medium,
        recovery_case_risk_status=RiskStatus.medium,
        recovery_case_current_state=RecoveryCaseState.open,
    )
    decision = PolicyEngine.evaluate_pre_policy(context_zero)
    assert decision.allowed is False
    assert "recoverable amount is 0" in decision.reason.lower()


def test_policy_enforces_human_review_for_high_risk():
    """Policy must enforce requires_human_review on high and critical risk cases."""
    context_high = RecoveryContext(
        recovery_case_id=4,
        revenue_record_id=4,
        payment_amount=5000000,  # 50,000 INR
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=5000000,
        recovery_case_priority=RecoveryPriority.urgent,
        recovery_case_risk_status=RiskStatus.critical,
        recovery_case_current_state=RecoveryCaseState.open,
    )
    pre_decision = PolicyEngine.evaluate_pre_policy(context_high)
    assert pre_decision.allowed is True
    assert pre_decision.requires_human_review is True

    # Even if LLM returns requires_human_review = False, post_policy must force True
    raw_rec = RawRecommendation(
        recommended_action_type=RecoveryActionType.email_reminder,
        recommended_channel=RecoveryActionChannel.email,
        confidence=0.9,
        rationale="Automated message",
        requires_human_review=False,
    )
    post_decision = PolicyEngine.evaluate_post_policy(context_high, raw_rec, pre_decision)
    assert post_decision.requires_human_review is True


def test_policy_blocks_excessive_retry_actions():
    """Policy must block retry_payment action if case has >= 3 prior actions."""
    context_retries = RecoveryContext(
        recovery_case_id=5,
        revenue_record_id=5,
        payment_amount=100000,
        currency="INR",
        payment_status=PaymentStatus.failed,
        revenue_status=RevenueStatus.at_risk,
        recoverable_amount=100000,
        recovery_case_priority=RecoveryPriority.medium,
        recovery_case_risk_status=RiskStatus.low,
        recovery_case_current_state=RecoveryCaseState.open,
        action_count=3,
    )
    pre = PolicyEngine.evaluate_pre_policy(context_retries)
    raw_rec = RawRecommendation(
        recommended_action_type=RecoveryActionType.retry_payment,
        recommended_channel=RecoveryActionChannel.system,
        confidence=0.7,
        rationale="Retrying payment direct API",
    )
    post = PolicyEngine.evaluate_post_policy(context_retries, raw_rec, pre)
    assert RecoveryActionType.retry_payment in post.blocked_actions


# ---------------------------------------------------------------------------
# 3. DECISION ENGINE SERVICE TESTS
# ---------------------------------------------------------------------------


def test_decision_engine_generates_recommendation(db_session, sample_case_setup):
    """Test generating a successful recommendation for an open recovery case."""
    rec = RecoveryDecisionEngine.generate_decision(db_session, sample_case_setup.id)

    assert rec.recovery_case_id == sample_case_setup.id
    assert rec.recommended_action_type == RecoveryActionType.payment_link
    assert rec.recommended_channel == RecoveryActionChannel.email
    assert 0.0 <= rec.confidence <= 1.0
    assert rec.is_blocked is False
    assert len(rec.rationale) > 0

    # Verify audit logs created
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_case", entity_id=str(sample_case_setup.id)
    )
    actions = [a.action for a in audits]
    assert "ai_recovery_decision_requested" in actions
    assert "ai_recovery_decision_generated" in actions


def test_decision_engine_blocked_case(db_session, sample_case_setup):
    """Test decision engine handles blocked terminal cases properly."""
    sample_case_setup.current_state = RecoveryCaseState.recovered
    db_session.commit()

    rec = RecoveryDecisionEngine.generate_decision(db_session, sample_case_setup.id)
    assert rec.is_blocked is True
    assert rec.recommended_action_type is None
    assert rec.confidence == 0.0
    assert "recovered" in rec.rationale.lower()

    # Verify audit log recorded block
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_case", entity_id=str(sample_case_setup.id)
    )
    actions = [a.action for a in audits]
    assert "ai_recovery_decision_blocked" in actions


def test_decision_engine_provider_failure_handling(db_session, sample_case_setup):
    """Test decision engine raises AIProviderError on provider failures."""
    failing_provider = MockAIProvider(force_failure=True)
    with pytest.raises(AIProviderError):
        RecoveryDecisionEngine.generate_decision(
            db_session, sample_case_setup.id, provider=failing_provider
        )


def test_decision_engine_non_destructive_guarantee(db_session, sample_case_setup):
    """
    CRITICAL SAFETY CHECK:
    Generating an AI decision must NOT mutate payment, revenue, or case status,
    and must NOT create a RecoveryAction in the database.
    """
    initial_payment_status = sample_case_setup.revenue_record.payment.status
    initial_revenue_status = sample_case_setup.revenue_record.status
    initial_case_state = sample_case_setup.current_state

    rec = RecoveryDecisionEngine.generate_decision(db_session, sample_case_setup.id)

    db_session.refresh(sample_case_setup)
    db_session.refresh(sample_case_setup.revenue_record)
    db_session.refresh(sample_case_setup.revenue_record.payment)

    assert sample_case_setup.revenue_record.payment.status == initial_payment_status
    assert sample_case_setup.revenue_record.status == initial_revenue_status
    assert sample_case_setup.current_state == initial_case_state

    # Verify NO RecoveryAction was created
    action_count = db_session.query(RecoveryAction).filter_by(recovery_case_id=sample_case_setup.id).count()
    assert action_count == 0


def test_decision_engine_case_not_found(db_session):
    """Test generating decision for non-existent case raises NotFoundError."""
    with pytest.raises(NotFoundError):
        RecoveryDecisionEngine.generate_decision(db_session, 99999)


# ---------------------------------------------------------------------------
# 4. REST API ENDPOINT TESTS
# ---------------------------------------------------------------------------


def test_api_generate_recovery_decision(client, db_session, sample_case_setup):
    """Test POST /api/v1/ai/recovery-cases/{case_id}/decision."""
    resp = client.post(f"/api/v1/ai/recovery-cases/{sample_case_setup.id}/decision")
    assert resp.status_code == 200

    data = resp.json()
    assert data["recovery_case_id"] == sample_case_setup.id
    assert data["recommended_action_type"] is not None
    assert data["recommended_channel"] is not None
    assert 0.0 <= data["confidence"] <= 1.0
    assert "policy_decision" in data
    assert data["policy_decision"]["allowed"] is True


def test_api_generate_recovery_decision_not_found(client):
    """Test POST /api/v1/ai/recovery-cases/99999/decision returns 404."""
    resp = client.post("/api/v1/ai/recovery-cases/99999/decision")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
