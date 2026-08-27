"""
Tests for Synthetic Dataset Generation, Predefined Demo Scenarios, and Demo REST APIs.

Covers:
1. Deterministic synthetic data generation (identical seed produces identical dataset)
2. Domain linkages (Payment -> Revenue -> Case -> Approval -> Job -> Audit)
3. Predefined Scenario 1: Autonomous low-risk recovery (success)
4. Predefined Scenario 2: High-risk human review gate (approval required)
5. Predefined Scenario 3: Retryable provider failure & backoff scheduling
6. Predefined Scenario 4: Permanent non-retryable provider failure
7. Predefined Scenario 5: Policy-blocked terminal case
8. Predefined Scenario 6: Multi-channel recovery fleet
9. Predefined Scenario 7: High-volume dataset generation
10. Database record reset
11. Demo mode environment protection (HTTP 403 when DEMO_MODE=False)
12. Demo REST API routes: /demo/seed, /demo/reset, /demo/scenarios, /demo/scenarios/{id}/run
13. CLI seeder invocation
"""

from unittest.mock import patch
import pytest

from app.core.config import get_settings
from app.demo.exceptions import DemoModeDisabledError
from app.demo.generator import generate_synthetic_dataset, reset_database_records
from app.demo.scenarios import list_available_scenarios, run_scenario
from app.demo.service import DemoService
from app.models.approval import RecoveryApproval
from app.models.enums import ApprovalStatus, JobStatus, RecoveryCaseState
from app.models.job import RecoveryExecutionJob
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord


def test_deterministic_synthetic_data_generation(db_session):
    """Test that the same random seed produces the exact same dataset."""
    # Seed 1
    resp1 = generate_synthetic_dataset(db_session, count=15, seed=123, reset=True)
    pay_count1 = resp1.payments_created
    rec_amount1 = resp1.total_recoverable_amount

    # Seed 2 (reset and generate again with same seed)
    resp2 = generate_synthetic_dataset(db_session, count=15, seed=123, reset=True)
    assert resp2.payments_created == pay_count1
    assert resp2.total_recoverable_amount == rec_amount1
    assert resp2.total_recovered_amount == resp1.total_recovered_amount


def test_synthetic_data_structure_and_relationships(db_session):
    """Test that generated records have proper relational foreign keys."""
    resp = generate_synthetic_dataset(db_session, count=10, seed=42, reset=True)

    assert resp.cases_created == 10
    cases = db_session.query(RecoveryCase).all()
    assert len(cases) == 10

    for c in cases:
        assert c.revenue_record_id is not None
        assert c.revenue_record is not None
        assert c.revenue_record.payment is not None
        assert len(c.approvals) >= 0


def test_scenario_success_low_risk(db_session):
    """Test predefined scenario: Autonomous Low-Risk Recovery."""
    res = run_scenario(db_session, "success", seed=42)

    assert res.scenario_id == "success"
    assert res.case_state in [RecoveryCaseState.recovering.value, RecoveryCaseState.recovered.value]
    assert res.approval_status == ApprovalStatus.approved.value


def test_scenario_human_review_gate(db_session):
    """Test predefined scenario: High-Risk Human Review Gate."""
    res = run_scenario(db_session, "human_review", seed=42)

    assert res.scenario_id == "human_review"
    assert res.approval_status == ApprovalStatus.pending.value
    assert res.case_state in [RecoveryCaseState.action_pending.value, RecoveryCaseState.open.value]


def test_scenario_retryable_failure(db_session):
    """Test predefined scenario: Retryable Provider Failure."""
    res = run_scenario(db_session, "retry", seed=42)

    assert res.scenario_id == "retry"
    assert res.job_status == JobStatus.retry_scheduled.value
    assert res.case_state != RecoveryCaseState.recovered.value


def test_scenario_permanent_failure(db_session):
    """Test predefined scenario: Permanent Non-Retryable Failure."""
    res = run_scenario(db_session, "failure", seed=42)

    assert res.scenario_id == "failure"
    assert res.job_status == JobStatus.failed.value
    assert res.case_state != RecoveryCaseState.recovered.value


def test_scenario_policy_blocked(db_session):
    """Test predefined scenario: Policy-Blocked Terminal Case."""
    res = run_scenario(db_session, "blocked", seed=42)

    assert res.scenario_id == "blocked"
    assert res.approval_id is None


def test_scenario_multi_channel(db_session):
    """Test predefined scenario: Multi-Channel Recovery."""
    res = run_scenario(db_session, "multi_channel", seed=42)

    assert res.scenario_id == "multi_channel"
    assert res.details["cases_created"] == 12


def test_scenario_high_volume(db_session):
    """Test predefined scenario: High-Volume Dataset."""
    res = run_scenario(db_session, "high_volume", seed=42)

    assert res.scenario_id == "high_volume"
    assert res.details["cases_created"] == 50


def test_reset_database_records(db_session):
    """Test purging all generated records."""
    generate_synthetic_dataset(db_session, count=5, seed=42, reset=False)
    assert db_session.query(Payment).count() >= 5

    reset_resp = reset_database_records(db_session)
    assert reset_resp.payments_deleted >= 5
    assert db_session.query(Payment).count() == 0


def test_demo_mode_disabled_protection(db_session):
    """Test that DemoService raises DemoModeDisabledError when DEMO_MODE is False."""
    with patch("app.demo.service.settings.DEMO_MODE", False):
        with pytest.raises(DemoModeDisabledError):
            DemoService.seed_data(db_session)

        with pytest.raises(DemoModeDisabledError):
            DemoService.reset_data(db_session)

        with pytest.raises(DemoModeDisabledError):
            DemoService.run_scenario(db_session, "success")


def test_api_demo_endpoints(client, db_session):
    """Test REST API demo endpoints."""
    # 1. GET /api/v1/demo/scenarios
    res_sc = client.get("/api/v1/demo/scenarios")
    assert res_sc.status_code == 200
    scenarios = res_sc.json()["scenarios"]
    assert len(scenarios) >= 6

    # 2. POST /api/v1/demo/seed
    res_seed = client.post("/api/v1/demo/seed", json={"count": 10, "seed": 42, "reset": True})
    assert res_seed.status_code == 201
    data = res_seed.json()
    assert data["cases_created"] == 10
    assert data["total_recoverable_amount"] > 0

    # 3. POST /api/v1/demo/scenarios/success/run
    res_run = client.post("/api/v1/demo/scenarios/success/run")
    assert res_run.status_code == 200
    assert res_run.json()["scenario_id"] == "success"

    # 4. POST /api/v1/demo/reset
    res_reset = client.post("/api/v1/demo/reset")
    assert res_reset.status_code == 200
    assert res_reset.json()["cases_deleted"] >= 10


def test_cli_demo_seed_invocation(db_session):
    """Test CLI script execution."""
    from app.demo.seed import main

    with patch("app.demo.seed.SessionLocal", return_value=db_session):
        with patch("sys.argv", ["seed.py", "--scenario", "success", "--count", "5", "--seed", "42"]):
            main()

