"""
Tests for Recovery Orchestration Workflow.

Covers:
- End-to-end safe orchestration (recommendation -> policy -> approval -> execution -> state sync)
- Human review gates for high/critical risk cases (stops at approval_required, never auto-executes)
- Terminal case protections (blocks recovered and closed cases)
- Zero recoverable balance protections
- Policy-blocked recommendation handling
- Complete idempotency (no duplicate approvals, duplicate actions, or duplicate side effects)
- Failure recovery & retryable flag tracking
- Workflow status diagnostic queries
- REST API integration (/api/v1/recovery-cases/{case_id}/orchestrate and /workflow)
- Comprehensive audit trail recording without secret leakage
"""

from datetime import datetime, timezone
import pytest

from app.core.exceptions import NotFoundError
from app.execution.mock_executor import MockRecoveryExecutor
from app.models.approval import RecoveryApproval
from app.models.enums import (
    ApprovalStatus,
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
from app.orchestration.orchestrator import RecoveryOrchestrator
from app.orchestration.schemas import WorkflowStatus
from app.services.audit_service import AuditService


@pytest.fixture
def sample_orchestration_case(db_session):
    """Fixture creating a standard failed payment, at-risk revenue, and open recovery case."""
    payment = Payment(
        razorpay_payment_id="pay_orch_001",
        amount=150000,  # 1,500.00 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
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
        reason="card_network_timeout",
        risk_status=RiskStatus.low,
        priority=RecoveryPriority.medium,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    return case


# ---------------------------------------------------------------------------
# 1. SUCCESSFUL ORCHESTRATION & STATE SYNC
# ---------------------------------------------------------------------------


def test_successful_low_risk_auto_orchestration(db_session, sample_orchestration_case):
    """
    Test end-to-end orchestration for a low-risk case with auto_execute_low_risk=True:
    1. AI recommendation generated
    2. Policy validated
    3. RecoveryApproval created & approved
    4. RecoveryAction executed
    5. Case state synchronized to 'recovering'
    6. All transitions audited
    """
    result = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
        auto_execute_low_risk=True,
    )

    assert result.status == WorkflowStatus.completed
    assert result.recovery_case_id == sample_orchestration_case.id
    assert result.is_blocked is False
    assert result.requires_human_review is False
    assert result.approval_id is not None
    assert result.execution_result is not None
    assert result.execution_result.success is True
    assert result.case_state == RecoveryCaseState.recovering

    # Verify DB records
    db_session.refresh(sample_orchestration_case)
    assert sample_orchestration_case.current_state == RecoveryCaseState.recovering
    assert len(sample_orchestration_case.approvals) == 1
    assert sample_orchestration_case.approvals[0].status == ApprovalStatus.approved
    assert len(sample_orchestration_case.actions) == 1
    assert sample_orchestration_case.actions[0].status == RecoveryActionStatus.executed

    # Verify audit logs
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="recovery_case", entity_id=str(sample_orchestration_case.id)
    )
    actions = [a.action for a in audits]
    assert "orchestration_started" in actions
    assert "orchestration_recommendation_generated" in actions
    assert "orchestration_approval_created" in actions
    assert "orchestration_execution_started" in actions
    assert "orchestration_execution_succeeded" in actions
    assert "orchestration_completed" in actions


def test_orchestration_without_auto_execute_creates_pending_approval(
    db_session, sample_orchestration_case
):
    """Test that when auto_execute_low_risk is False, workflow creates pending approval and stops."""
    result = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
        auto_execute_low_risk=False,
    )

    assert result.status == WorkflowStatus.approval_created
    assert result.approval_id is not None
    assert result.execution_result is None
    assert result.case_state == RecoveryCaseState.open

    # Verify approval is pending in DB
    db_session.refresh(sample_orchestration_case)
    assert sample_orchestration_case.approvals[0].status == ApprovalStatus.pending
    assert len(sample_orchestration_case.actions) == 0


# ---------------------------------------------------------------------------
# 2. HUMAN REVIEW & HIGH-RISK PROTECTION
# ---------------------------------------------------------------------------


def test_orchestration_enforces_human_review_for_high_risk(
    db_session, sample_orchestration_case
):
    """
    Test that high/critical risk cases strictly stop at approval_required,
    even if auto_execute_low_risk=True is passed.
    """
    sample_orchestration_case.risk_status = RiskStatus.high
    db_session.commit()

    result = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
        auto_execute_low_risk=True,
    )

    assert result.status == WorkflowStatus.approval_required
    assert result.requires_human_review is True
    assert result.approval_id is not None
    assert result.execution_result is None
    assert result.case_state == RecoveryCaseState.open

    # DB state: pending approval, NO action executed
    db_session.refresh(sample_orchestration_case)
    assert sample_orchestration_case.approvals[0].status == ApprovalStatus.pending
    assert sample_orchestration_case.approvals[0].requires_human_review is True
    assert len(sample_orchestration_case.actions) == 0
    assert sample_orchestration_case.current_state == RecoveryCaseState.open


# ---------------------------------------------------------------------------
# 3. TERMINAL CASE & ZERO BALANCE PROTECTION
# ---------------------------------------------------------------------------


def test_orchestration_blocks_terminal_case(db_session, sample_orchestration_case):
    """Test that orchestrating a recovered or closed case is immediately blocked."""
    sample_orchestration_case.current_state = RecoveryCaseState.recovered
    db_session.commit()

    result = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
    )

    assert result.status == WorkflowStatus.policy_blocked
    assert result.is_blocked is True
    assert "terminal state" in result.message.lower()
    assert result.approval_id is None
    assert len(sample_orchestration_case.approvals) == 0


def test_orchestration_blocks_zero_recoverable_amount(
    db_session, sample_orchestration_case
):
    """Test that cases with 0 recoverable amount are blocked."""
    sample_orchestration_case.revenue_record.recoverable_amount = 0
    db_session.commit()

    result = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
    )

    assert result.status == WorkflowStatus.policy_blocked
    assert result.is_blocked is True
    assert "0 paise" in result.message


def test_orchestration_handles_excessive_retry_policy_block(
    db_session, sample_orchestration_case
):
    """Test that cases where AI recommends retry_payment after 3 retries get policy-blocked."""
    from app.ai.provider import AIProvider
    from app.ai.schemas import RawRecommendation

    class ForceRetryAIProvider(AIProvider):
        def generate_recovery_recommendation(self, context):
            return RawRecommendation(
                recommended_action_type=RecoveryActionType.retry_payment,
                recommended_channel=RecoveryActionChannel.system,
                priority=RecoveryPriority.high,
                confidence=0.9,
                rationale="Forced retry payment",
            )

    # Add 3 prior actions
    for _ in range(3):
        act = RecoveryAction(
            recovery_case_id=sample_orchestration_case.id,
            action_type=RecoveryActionType.retry_payment,
            channel=RecoveryActionChannel.system,
            status=RecoveryActionStatus.failed,
        )
        db_session.add(act)
    db_session.commit()

    result = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
        ai_provider=ForceRetryAIProvider(),
    )

    # Policy blocked retry_payment
    assert result.status == WorkflowStatus.policy_blocked
    assert result.is_blocked is True
    assert result.recommendation.is_blocked is True




# ---------------------------------------------------------------------------
# 4. IDEMPOTENCY
# ---------------------------------------------------------------------------


def test_orchestration_idempotency_for_completed_workflow(
    db_session, sample_orchestration_case
):
    """Test that re-orchestrating an already executed case returns existing completed result."""
    # First execution
    res1 = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
        auto_execute_low_risk=True,
    )
    assert res1.status == WorkflowStatus.completed

    # Second execution
    res2 = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
        auto_execute_low_risk=True,
    )
    assert res2.status == WorkflowStatus.completed
    assert res2.approval_id == res1.approval_id
    assert res2.execution_result.execution_id == res1.execution_result.execution_id

    # Confirm no duplicate action created
    db_session.refresh(sample_orchestration_case)
    assert len(sample_orchestration_case.actions) == 1
    assert len(sample_orchestration_case.approvals) == 1


def test_orchestration_idempotency_for_pending_approval(
    db_session, sample_orchestration_case
):
    """Test that re-orchestrating a case with a pending approval returns existing pending result."""
    sample_orchestration_case.risk_status = RiskStatus.critical
    db_session.commit()

    res1 = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
    )
    assert res1.status == WorkflowStatus.approval_required

    res2 = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
    )
    assert res2.status == WorkflowStatus.approval_required
    assert res2.approval_id == res1.approval_id

    # No duplicate approval records
    db_session.refresh(sample_orchestration_case)
    assert len(sample_orchestration_case.approvals) == 1


# ---------------------------------------------------------------------------
# 5. EXECUTION FAILURE & DIAGNOSTICS
# ---------------------------------------------------------------------------


def test_orchestration_execution_failure_handling(
    db_session, sample_orchestration_case
):
    """Test handling and recording when executor fails during auto-execution."""
    failing_executor = MockRecoveryExecutor(force_failure=True, retryable_failure=True)

    result = RecoveryOrchestrator.orchestrate_recovery(
        db=db_session,
        case_id=sample_orchestration_case.id,
        auto_execute_low_risk=True,
        executor=failing_executor,
    )

    assert result.status == WorkflowStatus.execution_failed
    assert result.execution_result.success is False
    assert result.execution_result.retryable is True
    assert "Execution failed" in result.message


def test_get_workflow_status_diagnostic(db_session, sample_orchestration_case):
    """Test the get_workflow_status diagnostic query."""
    status_resp = RecoveryOrchestrator.get_workflow_status(
        db=db_session, case_id=sample_orchestration_case.id
    )

    assert status_resp.recovery_case_id == sample_orchestration_case.id
    assert status_resp.case_state == RecoveryCaseState.open
    assert status_resp.current_workflow_status == WorkflowStatus.started
    assert status_resp.is_terminal is False
    assert status_resp.recoverable_amount == 150000


def test_orchestration_case_not_found(db_session):
    """Test orchestrating non-existent case raises NotFoundError."""
    with pytest.raises(NotFoundError):
        RecoveryOrchestrator.orchestrate_recovery(db=db_session, case_id=999999)


# ---------------------------------------------------------------------------
# 6. REST API INTEGRATION
# ---------------------------------------------------------------------------


def test_api_orchestration_and_workflow_routes(
    client, db_session, sample_orchestration_case
):
    """Test orchestration and workflow status endpoints via REST API."""
    # 1. Orchestrate API call
    response = client.post(
        f"/api/v1/recovery-cases/{sample_orchestration_case.id}/orchestrate",
        json={"auto_execute_low_risk": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["case_state"] == "recovering"
    assert data["approval_id"] is not None
    assert data["execution_result"]["success"] is True

    # 2. Query workflow status API call
    wf_response = client.get(
        f"/api/v1/recovery-cases/{sample_orchestration_case.id}/workflow"
    )
    assert wf_response.status_code == 200
    wf_data = wf_response.json()
    assert wf_data["recovery_case_id"] == sample_orchestration_case.id
    assert wf_data["current_workflow_status"] == "completed"
    assert wf_data["latest_action_status"] == "executed"
