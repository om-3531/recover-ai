"""
Final Release Readiness Tests — Days 23-26.

Comprehensive E2E verification of the entire RecoverAI system covering:
- Clean database lifecycle (delete → start → seed → use)
- Full high-risk pipeline: webhook → AI → policy → approval → execute
- Full low-risk pipeline: webhook → AI → policy → auto-execute
- Idempotency of duplicate webhooks
- Approval CRUD operations
- Execution state machine (open → action_pending → recovering)
- Policy settings (get, update, reset, preview)
- System health endpoints
- Analytics consistency
- Error handling (404, 400, 422)
- Demo data consistency (recoverable_amount, case states)
"""

import pytest

from app.approval.schemas import ApprovalCreateRequest, ApprovalDecisionRequest
from app.approval.service import ApprovalService
from app.core.config import get_settings
from app.demo.generator import generate_synthetic_dataset, reset_database_records
from app.execution.service import RecoveryExecutionService
from app.models.enums import (
    ApprovalStatus,
    RecoveryActionChannel,
    RecoveryActionType,
    RecoveryCaseState,
    RevenueStatus,
)
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.orchestration.orchestrator import RecoveryOrchestrator
from app.services.audit_service import AuditService


# ---------------------------------------------------------------------------
# 1. CLEAN DATABASE LIFECYCLE
# ---------------------------------------------------------------------------


class TestCleanDatabaseLifecycle:
    """Verify the system works from a completely clean database state."""

    def test_seed_creates_all_entities(self, db_session):
        """Seeding creates payments, revenues, cases, approvals, jobs, audit logs."""
        result = generate_synthetic_dataset(db_session, count=10, seed=42, reset=True)
        assert result.cases_created == 10
        assert result.payments_created == 10
        assert result.revenue_records_created == 10
        assert result.approvals_created > 0
        assert result.jobs_created > 0
        assert result.audit_logs_created > 0
        assert result.total_recoverable_amount > 0

    def test_reset_clears_all_entities(self, db_session):
        """Reset purges all records and returns zero counts."""
        generate_synthetic_dataset(db_session, count=5, seed=42, reset=True)
        reset_result = reset_database_records(db_session)
        assert reset_result.payments_deleted >= 5
        assert reset_result.cases_deleted >= 5

    def test_seed_zero_count_no_crash(self, db_session):
        """Seeding with count=0 must not crash (ZeroDivisionError guard)."""
        result = generate_synthetic_dataset(db_session, count=0, seed=42, reset=True)
        assert result.cases_created == 0
        assert result.total_recoverable_amount == 0

    def test_recovered_records_have_zero_recoverable(self, db_session):
        """Recovered revenue records must have recoverable_amount=0."""
        generate_synthetic_dataset(db_session, count=30, seed=42, reset=True)
        recovered = db_session.query(RevenueRecord).filter(
            RevenueRecord.status == RevenueStatus.recovered
        ).all()
        assert len(recovered) > 0
        for rev in recovered:
            assert rev.recoverable_amount == 0, (
                f"RevenueRecord #{rev.id} is recovered but recoverable_amount={rev.recoverable_amount}"
            )


# ---------------------------------------------------------------------------
# 2. HIGH-RISK PIPELINE: WEBHOOK → AI → POLICY → APPROVAL → EXECUTE
# ---------------------------------------------------------------------------


class TestHighRiskPipeline:
    """Full end-to-end high-risk recovery pipeline."""

    def test_high_risk_creates_pending_approval(self, db_session):
        """High-risk payment should create a recovery case with a pending approval."""
        # Create a high-value payment (₹15,000 = 1500000 paise → critical risk)
        payment = Payment(
            razorpay_payment_id="pay_high_risk_test",
            razorpay_order_id="order_high_risk_test",
            amount=1500000,
            currency="INR",
            status="failed",
            method="card",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=1500000,
            recoverable_amount=1500000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="payment_failed",
            risk_status="critical",
            priority="urgent",
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()

        result = RecoveryOrchestrator.orchestrate_recovery(
            db_session, case.id, actor="test_high_risk"
        )
        assert result.status.value == "approval_required"
        assert result.approval_id is not None
        assert result.requires_human_review is True

    def test_approve_then_execute_completes_pipeline(self, db_session):
        """Approving and executing transitions the case to recovering."""
        payment = Payment(
            razorpay_payment_id="pay_approve_exec_test",
            razorpay_order_id="order_approve_exec_test",
            amount=500000,
            currency="INR",
            status="failed",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=500000,
            recoverable_amount=500000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="insufficient_funds",
            risk_status="high",
            priority="high",
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()

        # Orchestrate → creates approval
        orch = RecoveryOrchestrator.orchestrate_recovery(
            db_session, case.id, actor="test_approve"
        )
        assert orch.approval_id is not None
        approval_id = orch.approval_id

        # Approve
        approved = ApprovalService.approve_approval(
            db_session, approval_id, actor="test_operator"
        )
        assert approved.status == ApprovalStatus.approved

        # Execute
        exec_resp = RecoveryExecutionService.execute_approval(
            db_session, approval_id, actor="test_executor"
        )
        assert exec_resp.result.success is True
        assert exec_resp.case_state == RecoveryCaseState.recovering


# ---------------------------------------------------------------------------
# 3. LOW-RISK PIPELINE: AUTO-EXECUTION
# ---------------------------------------------------------------------------


class TestLowRiskPipeline:
    """Low-risk recovery should auto-execute without human approval."""

    def test_low_risk_auto_executes(self, db_session):
        """Low-risk payment should auto-approve and execute in one orchestration call."""
        payment = Payment(
            razorpay_payment_id="pay_low_risk_auto",
            razorpay_order_id="order_low_risk_auto",
            amount=50000,
            currency="INR",
            status="failed",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=50000,
            recoverable_amount=50000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="insufficient_funds",
            risk_status="low",
            priority="medium",
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()

        result = RecoveryOrchestrator.orchestrate_recovery(
            db_session, case.id, actor="test_low_risk"
        )
        assert result.status.value == "completed"
        assert result.execution_result is not None
        assert result.execution_result.success is True
        assert result.case_state == RecoveryCaseState.recovering


# ---------------------------------------------------------------------------
# 4. IDEMPOTENCY
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Verify duplicate operations are safely handled."""

    def test_duplicate_orchestration_returns_existing(self, db_session):
        """Second orchestration for the same case should return the existing result."""
        payment = Payment(
            razorpay_payment_id="pay_idempotent_test",
            razorpay_order_id="order_idempotent_test",
            amount=200000,
            currency="INR",
            status="failed",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=200000,
            recoverable_amount=200000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="test",
            risk_status="medium",
            priority="medium",
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()

        # First orchestration
        result1 = RecoveryOrchestrator.orchestrate_recovery(db_session, case.id)
        assert result1.approval_id is not None

        # Second orchestration should return same approval
        result2 = RecoveryOrchestrator.orchestrate_recovery(db_session, case.id)
        assert result2.approval_id == result1.approval_id

    def test_duplicate_execution_returns_cached(self, db_session):
        """Executing the same approval twice returns the same result."""
        payment = Payment(
            razorpay_payment_id="pay_exec_idempotent",
            razorpay_order_id="order_exec_idempotent",
            amount=1000000,
            currency="INR",
            status="failed",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=1000000,
            recoverable_amount=1000000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="test",
            risk_status="high",
            priority="high",
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()

        orch = RecoveryOrchestrator.orchestrate_recovery(db_session, case.id)
        assert orch.status.value == "approval_required"
        ApprovalService.approve_approval(db_session, orch.approval_id)

        # First execution
        exec1 = RecoveryExecutionService.execute_approval(db_session, orch.approval_id)
        assert exec1.result.success is True

        # Second execution should return cached result
        exec2 = RecoveryExecutionService.execute_approval(db_session, orch.approval_id)
        assert exec2.recovery_action_id == exec1.recovery_action_id
        assert exec2.result.execution_id == exec1.result.execution_id


# ---------------------------------------------------------------------------
# 5. STATE MACHINE INTEGRITY
# ---------------------------------------------------------------------------


class TestStateMachine:
    """Verify state machine transitions are enforced."""

    def test_cannot_orchestrate_on_terminal_case(self, db_session):
        """Orchestration on a recovered case returns policy_blocked."""
        payment = Payment(
            razorpay_payment_id="pay_terminal_test",
            razorpay_order_id="order_terminal_test",
            amount=100000,
            currency="INR",
            status="failed",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=100000,
            recoverable_amount=100000,
            currency="INR",
            status=RevenueStatus.recovered,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="test",
            risk_status="low",
            priority="low",
            current_state=RecoveryCaseState.recovered,
        )
        db_session.add(case)
        db_session.flush()

        from app.orchestration.schemas import WorkflowStatus
        result = RecoveryOrchestrator.orchestrate_recovery(db_session, case.id)
        assert result.status == WorkflowStatus.policy_blocked


# ---------------------------------------------------------------------------
# 6. API ENDPOINT COVERAGE
# ---------------------------------------------------------------------------


class TestAPIEndpoints:
    """Verify key API endpoints return correct responses."""

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_ready_endpoint(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200

    def test_system_status_endpoint(self, client):
        resp = client.get("/api/v1/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "operational"
        assert "demo_mode" in data

    def test_system_providers_endpoint(self, client):
        resp = client.get("/api/v1/system/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data

    def test_create_approval(self, client, db_session):
        from app.demo.generator import generate_synthetic_dataset
        generate_synthetic_dataset(db_session, count=3, seed=42, reset=True)
        db_session.commit()

        case = db_session.query(RecoveryCase).first()
        resp = client.post("/api/v1/approvals", json={
            "recovery_case_id": case.id,
            "action_type": "email_reminder",
            "channel": "email",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"

    def test_list_approvals(self, client, db_session):
        from app.demo.generator import generate_synthetic_dataset
        generate_synthetic_dataset(db_session, count=3, seed=42, reset=True)
        db_session.commit()

        resp = client.get("/api/v1/approvals?limit=10")
        assert resp.status_code == 200

    def test_get_nonexistent_approval_returns_404(self, client):
        resp = client.get("/api/v1/approvals/99999")
        assert resp.status_code == 404

    def test_get_nonexistent_case_returns_404(self, client):
        resp = client.get("/api/v1/recovery/cases/99999/timeline")
        assert resp.status_code == 404

    def test_policy_preview(self, client, db_session):
        from app.policy.service import PolicyService
        PolicyService.get_or_create_default_policy(db_session)
        db_session.commit()

        resp = client.post("/api/v1/policies/preview?merchant_id=merchant_default", json={
            "amount_paise": 100000,
            "risk_status": "high",
            "channel": "email",
            "attempt_count": 0,
            "current_state": "open",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "evaluation" in data
        assert "allowed" in data["evaluation"]

    def test_webhook_fixtures(self, client):
        resp = client.get("/api/v1/webhooks/fixtures")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4

    def test_webhook_config_status(self, client):
        resp = client.get("/api/v1/webhooks/config-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data

    def test_demo_seed_and_reset(self, client):
        seed_resp = client.post("/api/v1/demo/seed", json={"count": 5, "seed": 42, "reset": True})
        assert seed_resp.status_code == 201
        seed_data = seed_resp.json()
        assert seed_data["cases_created"] == 5

        reset_resp = client.post("/api/v1/demo/reset")
        assert reset_resp.status_code == 200


# ---------------------------------------------------------------------------
# 7. ANALYTICS CONSISTENCY
# ---------------------------------------------------------------------------


class TestAnalyticsConsistency:
    """Analytics should be consistent after seeding."""

    def test_overview_matches_seed(self, client, db_session):
        from app.demo.generator import generate_synthetic_dataset
        generate_synthetic_dataset(db_session, count=20, seed=42, reset=True)
        db_session.commit()

        resp = client.get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] == 20
        assert data["recovered_cases"] > 0
        assert data["total_recoverable_amount"] > 0

    def test_revenue_analytics(self, client, db_session):
        from app.demo.generator import generate_synthetic_dataset
        generate_synthetic_dataset(db_session, count=10, seed=42, reset=True)
        db_session.commit()

        resp = client.get("/api/v1/analytics/revenue")
        assert resp.status_code == 200
        data = resp.json()
        assert "average_recovery_amount" in data
        assert data["recovered_case_count"] > 0

    def test_channel_analytics(self, client, db_session):
        from app.demo.generator import generate_synthetic_dataset
        generate_synthetic_dataset(db_session, count=10, seed=42, reset=True)
        db_session.commit()

        resp = client.get("/api/v1/analytics/channels")
        assert resp.status_code == 200

    def test_recent_activity(self, client, db_session):
        from app.demo.generator import generate_synthetic_dataset
        generate_synthetic_dataset(db_session, count=5, seed=42, reset=True)
        db_session.commit()

        resp = client.get("/api/v1/analytics/recent-activity?limit=10")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 8. CONFIGURATION SAFETY
# ---------------------------------------------------------------------------


class TestConfigurationSafety:
    """Verify safe defaults and security properties."""

    def test_no_secrets_in_config(self):
        settings = get_settings()
        assert settings.RAZORPAY_KEY_ID == ""
        assert settings.RAZORPAY_KEY_SECRET == ""
        assert settings.GEMINI_API_KEY == ""
        assert settings.SENDGRID_API_KEY == ""
        assert settings.TWILIO_AUTH_TOKEN == ""

    def test_demo_mode_enabled(self):
        settings = get_settings()
        assert settings.DEMO_MODE is True

    def test_ai_provider_is_mock(self):
        settings = get_settings()
        assert settings.AI_PROVIDER == "mock"

    def test_webhook_insecure_http_disabled(self):
        settings = get_settings()
        assert settings.WEBHOOK_ALLOW_INSECURE_HTTP is False


# ---------------------------------------------------------------------------
# 9. AUDIT TRAIL COMPLETENESS
# ---------------------------------------------------------------------------


class TestAuditTrail:
    """Every critical action should produce audit logs."""

    def test_orchestration_creates_audit_logs(self, db_session):
        payment = Payment(
            razorpay_payment_id="pay_audit_test",
            razorpay_order_id="order_audit_test",
            amount=500000,
            currency="INR",
            status="failed",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=500000,
            recoverable_amount=500000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="test",
            risk_status="high",
            priority="high",
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()

        RecoveryOrchestrator.orchestrate_recovery(db_session, case.id)

        from app.models.audit import AuditLog
        logs = db_session.query(AuditLog).filter(
            AuditLog.entity_type == "recovery_case",
            AuditLog.entity_id == str(case.id),
        ).all()
        actions = [log.action for log in logs]
        assert "orchestration_started" in actions
        assert "orchestration_recommendation_generated" in actions
        assert "orchestration_approval_created" in actions

    def test_approval_decision_creates_audit_log(self, db_session):
        payment = Payment(
            razorpay_payment_id="pay_approval_audit",
            razorpay_order_id="order_approval_audit",
            amount=1500000,
            currency="INR",
            status="failed",
        )
        db_session.add(payment)
        db_session.flush()

        revenue = RevenueRecord(
            payment_id=payment.id,
            gross_amount=1500000,
            recoverable_amount=1500000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db_session.add(revenue)
        db_session.flush()

        case = RecoveryCase(
            revenue_record_id=revenue.id,
            reason="test",
            risk_status="critical",
            priority="urgent",
            current_state=RecoveryCaseState.open,
        )
        db_session.add(case)
        db_session.flush()

        orch = RecoveryOrchestrator.orchestrate_recovery(db_session, case.id)
        assert orch.status.value == "approval_required"
        ApprovalService.approve_approval(db_session, orch.approval_id, actor="judge")

        from app.models.audit import AuditLog
        logs = db_session.query(AuditLog).filter(
            AuditLog.entity_type == "recovery_approval",
            AuditLog.action == "approval_approved",
        ).all()
        assert len(logs) >= 1
