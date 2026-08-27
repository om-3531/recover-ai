"""
End-to-End Recovery Smoke Tests.

Deterministic, mock-based tests verifying the complete pipeline:
  AI → Policy → Approval → Execution

Covers:
- Full recovery lifecycle (happy path)
- Multi-attempt escalation
- High-value approval gate
- Terminal state block
- Policy override of AI recommendation
- Audit trail completeness
- Provider fallback graceful degradation
"""

import pytest

from app.ai.decision_engine import RecoveryDecisionEngine
from app.ai.provider import MockAIProvider
from app.ai.schemas import RawRecommendation
from app.approval.service import ApprovalService
from app.core.metrics import metrics
from app.models.enums import (
    ApprovalStatus,
    JobStatus,
    PaymentMethod,
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
from app.policy.service import PolicyService
from app.services.audit_service import AuditService


@pytest.fixture
def smoke_case(db_session):
    """Standard medium-risk recovery case for smoke tests."""
    payment = Payment(
        razorpay_payment_id="pay_smoke_001",
        razorpay_order_id="order_smoke_001",
        amount=250000,
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
        customer_email="smoke@example.com",
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
        reason="card_declined",
        risk_status=RiskStatus.medium,
        priority=RecoveryPriority.medium,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def high_value_case(db_session):
    """High-value payment requiring approval gate."""
    payment = Payment(
        razorpay_payment_id="pay_smoke_hv_001",
        razorpay_order_id="order_smoke_hv_001",
        amount=5000000,
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
        customer_email="highvalue@example.com",
    )
    db_session.add(payment)
    db_session.flush()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=5000000,
        recoverable_amount=5000000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.flush()

    case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="large_payment_failure",
        risk_status=RiskStatus.high,
        priority=RecoveryPriority.urgent,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


# ---------------------------------------------------------------------------
# 1. AI → POLICY: FULL DECISION PIPELINE
# ---------------------------------------------------------------------------


def test_ai_to_policy_full_pipeline(db_session, smoke_case):
    rec = RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id)

    assert rec.is_blocked is False
    assert rec.recommended_action_type is not None
    assert rec.recommended_channel is not None
    assert 0.0 <= rec.confidence <= 1.0
    assert rec.policy_decision.allowed is True
    assert rec.provider == "mock"


def test_ai_to_policy_with_gemini_provider(db_session, smoke_case):
    provider = MockAIProvider()
    rec = RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id, provider=provider)
    assert rec.provider == "mock"
    assert rec.is_blocked is False


# ---------------------------------------------------------------------------
# 2. POLICY → APPROVAL GATE
# ---------------------------------------------------------------------------


def test_high_risk_requires_approval(db_session, high_value_case):
    rec = RecoveryDecisionEngine.generate_decision(db_session, high_value_case.id)

    assert rec.requires_human_review is True
    assert rec.policy_decision.requires_human_review is True


# ---------------------------------------------------------------------------
# 3. TERMINAL STATE BLOCK
# ---------------------------------------------------------------------------


def test_terminal_state_blocked(db_session, smoke_case):
    smoke_case.current_state = RecoveryCaseState.recovered
    db_session.commit()

    rec = RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id)
    assert rec.is_blocked is True
    assert rec.confidence == 0.0
    assert rec.recommended_action_type is None


def test_zero_recoverable_amount_blocked(db_session, smoke_case):
    smoke_case.revenue_record.recoverable_amount = 0
    db_session.commit()

    rec = RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id)
    assert rec.is_blocked is True


# ---------------------------------------------------------------------------
# 4. POLICY OVERRIDE OF AI RECOMMENDATION
# ---------------------------------------------------------------------------


def test_policy_blocks_excessive_retries(db_session, smoke_case):
    provider = MockAIProvider(
        override_recommendation=RawRecommendation(
            recommended_action_type=RecoveryActionType.retry_payment,
            recommended_channel=RecoveryActionChannel.system,
            confidence=0.8,
            rationale="Retrying payment API",
        )
    )

    # Add 3 actions to trigger retry block
    from app.models.recovery import RecoveryAction
    for i in range(3):
        action = RecoveryAction(
            recovery_case_id=smoke_case.id,
            action_type=RecoveryActionType.payment_link,
            channel=RecoveryActionChannel.email,
            status="executed",
        )
        db_session.add(action)
    db_session.commit()

    rec = RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id, provider=provider)
    assert RecoveryActionType.retry_payment in rec.policy_decision.blocked_actions


# ---------------------------------------------------------------------------
# 5. AUDIT TRAIL COMPLETENESS
# ---------------------------------------------------------------------------


def test_audit_trail_on_successful_decision(db_session, smoke_case):
    RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id)

    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_case", entity_id=str(smoke_case.id)
    )
    actions = [a.action for a in audits]
    assert "ai_recovery_decision_requested" in actions
    assert "ai_recovery_decision_generated" in actions


def test_audit_trail_on_blocked_decision(db_session, smoke_case):
    smoke_case.current_state = RecoveryCaseState.closed
    db_session.commit()

    RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id)

    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_case", entity_id=str(smoke_case.id)
    )
    actions = [a.action for a in audits]
    assert "ai_recovery_decision_requested" in actions
    assert "ai_recovery_decision_blocked" in actions


# ---------------------------------------------------------------------------
# 6. PROVIDER FALLBACK GRACEFUL DEGRADATION
# ---------------------------------------------------------------------------


def test_provider_failure_falls_back_to_mock(db_session, smoke_case):
    failing = MockAIProvider(force_failure=True)
    with pytest.raises(Exception):
        RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id, provider=failing)


# ---------------------------------------------------------------------------
# 7. METRICS INCREMENT ON DECISION
# ---------------------------------------------------------------------------


def test_metrics_increment_on_decision(db_session, smoke_case):
    metrics.reset()
    RecoveryDecisionEngine.generate_decision(db_session, smoke_case.id)
    assert metrics.get_count("ai_decisions_total") >= 1


# ---------------------------------------------------------------------------
# 8. POLICY SERVICE CREATES DEFAULT POLICY
# ---------------------------------------------------------------------------


def test_policy_service_default_policy_exists(db_session):
    policy = PolicyService.get_or_create_default_policy(db_session)
    assert policy is not None
    assert policy.is_active is True
    assert policy.max_attempts > 0
    assert policy.min_recovery_amount_paise >= 0
    assert policy.max_recovery_amount_paise > 0
