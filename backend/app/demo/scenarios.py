"""
Predefined end-to-end demo scenarios for buildathon presentation and testing.
"""

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.demo.generator import generate_synthetic_dataset
from app.demo.schemas import DemoScenarioInfo, DemoScenarioRunResponse
from app.jobs.service import JobService
from app.models.approval import RecoveryApproval
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
from app.providers.email import MockEmailProvider
from app.providers.registry import ProviderRegistry
from app.services.audit_service import AuditService

AVAILABLE_SCENARIOS: List[DemoScenarioInfo] = [
    DemoScenarioInfo(
        id="success",
        name="1. Autonomous Low-Risk Recovery",
        description="Payment failure with low risk. AI recommends email reminder, policy permits auto-approval, mock provider dispatches successfully, and case transitions to recovering.",
        risk_level="low",
        channel="email",
        expected_outcome="Job succeeded • Case recovering • Revenue recoverable",
    ),
    DemoScenarioInfo(
        id="human_review",
        name="2. High-Risk Human Review Gate",
        description="High-value payment failure (₹15,000). Policy engine strictly mandates human supervisor authorization. System stops at approval_required with pending approval.",
        risk_level="high",
        channel="sms",
        expected_outcome="Approval pending • Human review required • Zero unapproved execution",
    ),
    DemoScenarioInfo(
        id="retry",
        name="3. Retryable Provider Failure with Exponential Backoff",
        description="Provider temporary network timeout. Job enters retry_scheduled status with calculated exponential next_retry_at. Case is not falsely marked recovered.",
        risk_level="medium",
        channel="email",
        expected_outcome="Job retry_scheduled • Backoff timestamp scheduled • Safe state",
    ),
    DemoScenarioInfo(
        id="failure",
        name="4. Permanent Non-Retryable Failure",
        description="Provider returns permanent non-retryable error (e.g. invalid recipient). Job immediately fails without endless retry loops.",
        risk_level="low",
        channel="whatsapp",
        expected_outcome="Job failed • Action failed • Case remains unrecovered",
    ),
    DemoScenarioInfo(
        id="blocked",
        name="5. Policy-Blocked Terminal Case",
        description="Attempting recovery on an already closed or terminal case. Deterministic policy engine blocks intervention before AI execution.",
        risk_level="low",
        channel="system",
        expected_outcome="Orchestration blocked • Policy check failed • Zero actions created",
    ),
    DemoScenarioInfo(
        id="multi_channel",
        name="6. Multi-Channel Dispatch Fleet",
        description="Fires 4 concurrent recovery workflows across Email, SMS, WhatsApp, and Webhook channels to populate channel metrics.",
        risk_level="various",
        channel="all",
        expected_outcome="4 distinct channel executions recorded in telemetry",
    ),
    DemoScenarioInfo(
        id="high_volume",
        name="7. High-Volume Dashboard Dataset",
        description="Generates 50+ synthetic payments, recovery cases, approvals, and jobs spanning the last 30 days for rich dashboard visualization.",
        risk_level="various",
        channel="all",
        expected_outcome="Full 30-day time-series telemetry seeded",
    ),
]


def list_available_scenarios() -> List[DemoScenarioInfo]:
    """Returns all available demo scenario definitions."""
    return AVAILABLE_SCENARIOS


def _get_unique_payment_id(db: Session, base_id: str) -> str:
    existing = db.query(Payment.id).filter(Payment.razorpay_payment_id == base_id).first()
    if existing is not None:
        import time
        return f"{base_id}_{int(time.time() * 1000) % 1000000}"
    return base_id


def run_scenario(db: Session, scenario_id: str, seed: int = 42) -> DemoScenarioRunResponse:
    """Executes a specific end-to-end recovery scenario."""
    now = datetime.now(timezone.utc)

    if scenario_id == "success":
        # 1. Low risk auto recovery
        p = Payment(
            razorpay_payment_id=_get_unique_payment_id(db, f"pay_demo_succ_{seed}"),
            amount=250000,  # ₹2,500.00
            currency="INR",
            status=PaymentStatus.failed,
            method=PaymentMethod.card,
            customer_email="alice@demo-customer.example",
            customer_reference="+919876543201",
        )
        db.add(p)
        db.flush()

        r = RevenueRecord(
            payment_id=p.id,
            gross_amount=250000,
            recoverable_amount=250000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db.add(r)
        db.flush()

        c = RecoveryCase(
            revenue_record_id=r.id,
            reason="card_network_timeout",
            risk_status=RiskStatus.low,
            priority=RecoveryPriority.medium,
            current_state=RecoveryCaseState.open,
        )
        db.add(c)
        db.commit()

        # Orchestrate
        result = RecoveryOrchestrator.orchestrate_recovery(db=db, case_id=c.id, auto_execute_low_risk=True)

        return DemoScenarioRunResponse(
            scenario_id="success",
            scenario_name="Autonomous Low-Risk Recovery",
            payment_id=p.id,
            case_id=c.id,
            approval_id=result.approval_id,
            job_id=None,
            case_state=result.case_state.value,
            approval_status=ApprovalStatus.approved.value,
            job_status="succeeded" if result.execution_result and result.execution_result.success else None,
            message="Payment failed → AI diagnosed → Policy auto-approved → Email provider dispatched → Case recovering.",
            details={"recoverable_amount": 250000, "channel": "email", "orchestration_status": result.status.value},
        )

    elif scenario_id == "human_review":
        # 2. High risk case requiring human review
        p = Payment(
            razorpay_payment_id=_get_unique_payment_id(db, f"pay_demo_high_{seed}"),
            amount=1500000,  # ₹15,000.00
            currency="INR",
            status=PaymentStatus.failed,
            method=PaymentMethod.upi,
            customer_email="bob@demo-enterprise.example",
            customer_reference="+919876543202",
        )
        db.add(p)
        db.flush()

        r = RevenueRecord(
            payment_id=p.id,
            gross_amount=1500000,
            recoverable_amount=1500000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db.add(r)
        db.flush()

        c = RecoveryCase(
            revenue_record_id=r.id,
            reason="insufficient_funds",
            risk_status=RiskStatus.high,
            priority=RecoveryPriority.urgent,
            current_state=RecoveryCaseState.open,
        )
        db.add(c)
        db.commit()

        result = RecoveryOrchestrator.orchestrate_recovery(db=db, case_id=c.id, auto_execute_low_risk=True)

        return DemoScenarioRunResponse(
            scenario_id="human_review",
            scenario_name="High-Risk Human Review Gate",
            payment_id=p.id,
            case_id=c.id,
            approval_id=result.approval_id,
            case_state=result.case_state.value,
            approval_status=ApprovalStatus.pending.value,
            message="High-risk case detected (₹15,000). Deterministic policy engine blocked auto-execution; pending human review.",
            details={"requires_human_review": True, "approval_status": "pending"},
        )

    elif scenario_id == "retry":
        # 3. Retryable provider failure
        p = Payment(
            razorpay_payment_id=_get_unique_payment_id(db, f"pay_demo_retry_{seed}"),
            amount=350000,
            currency="INR",
            status=PaymentStatus.failed,
            method=PaymentMethod.card,
            customer_email="charlie@demo.example",
            customer_reference="+919876543203",
        )
        db.add(p)
        db.flush()

        r = RevenueRecord(
            payment_id=p.id,
            gross_amount=350000,
            recoverable_amount=350000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db.add(r)
        db.flush()

        c = RecoveryCase(
            revenue_record_id=r.id,
            reason="card_network_timeout",
            risk_status=RiskStatus.medium,
            priority=RecoveryPriority.high,
            current_state=RecoveryCaseState.open,
        )
        db.add(c)
        db.flush()

        appr = RecoveryApproval(
            recovery_case_id=c.id,
            action_type=RecoveryActionType.email_reminder,
            channel=RecoveryActionChannel.email,
            status=ApprovalStatus.approved,
            approved_by="demo_supervisor",
            requested_at=now,
            approved_at=now,
        )
        db.add(appr)
        db.commit()

        # Inject failing retryable provider
        reg = ProviderRegistry()
        reg.register(RecoveryActionChannel.email, MockEmailProvider(force_failure=True, retryable_failure=True))

        job = JobService.create_job(db=db, approval_id=appr.id, auto_process=True, registry=reg)

        return DemoScenarioRunResponse(
            scenario_id="retry",
            scenario_name="Retryable Provider Failure with Exponential Backoff",
            payment_id=p.id,
            case_id=c.id,
            approval_id=appr.id,
            job_id=job.id,
            case_state=c.current_state.value,
            approval_status=appr.status.value,
            job_status=job.status.value,
            message="Provider encountered a temporary timeout. Job scheduled for retry with exponential backoff.",
            details={"attempt_count": job.attempt_count, "next_retry_at": str(job.next_retry_at), "error_code": job.error_code},
        )

    elif scenario_id == "failure":
        # 4. Permanent failure
        p = Payment(
            razorpay_payment_id=_get_unique_payment_id(db, f"pay_demo_fail_{seed}"),
            amount=400000,
            currency="INR",
            status=PaymentStatus.failed,
            method=PaymentMethod.card,
            customer_email="david@invalid-domain.example",
            customer_reference="+919876543204",
        )
        db.add(p)
        db.flush()

        r = RevenueRecord(
            payment_id=p.id,
            gross_amount=400000,
            recoverable_amount=400000,
            currency="INR",
            status=RevenueStatus.at_risk,
        )
        db.add(r)
        db.flush()

        c = RecoveryCase(
            revenue_record_id=r.id,
            reason="authentication_failed",
            risk_status=RiskStatus.low,
            priority=RecoveryPriority.medium,
            current_state=RecoveryCaseState.open,
        )
        db.add(c)
        db.flush()

        appr = RecoveryApproval(
            recovery_case_id=c.id,
            action_type=RecoveryActionType.email_reminder,
            channel=RecoveryActionChannel.email,
            status=ApprovalStatus.approved,
            approved_by="demo_supervisor",
            requested_at=now,
            approved_at=now,
        )
        db.add(appr)
        db.commit()

        reg = ProviderRegistry()
        reg.register(RecoveryActionChannel.email, MockEmailProvider(force_failure=True, retryable_failure=False))

        job = JobService.create_job(db=db, approval_id=appr.id, auto_process=True, registry=reg)

        return DemoScenarioRunResponse(
            scenario_id="failure",
            scenario_name="Permanent Non-Retryable Failure",
            payment_id=p.id,
            case_id=c.id,
            approval_id=appr.id,
            job_id=job.id,
            case_state=c.current_state.value,
            approval_status=appr.status.value,
            job_status=job.status.value,
            message="Permanent provider error detected. Job marked failed; case safely remains unrecovered.",
            details={"attempt_count": job.attempt_count, "error_code": job.error_code},
        )

    elif scenario_id == "blocked":
        # 5. Policy blocked
        p = Payment(
            razorpay_payment_id=_get_unique_payment_id(db, f"pay_demo_blk_{seed}"),
            amount=100000,
            currency="INR",
            status=PaymentStatus.captured,
            method=PaymentMethod.card,
            customer_email="eve@demo.example",
            customer_reference="+919876543205",
        )
        db.add(p)
        db.flush()

        r = RevenueRecord(
            payment_id=p.id,
            gross_amount=100000,
            recoverable_amount=0,  # Zero recoverable balance
            currency="INR",
            status=RevenueStatus.recovered,
        )
        db.add(r)
        db.flush()

        c = RecoveryCase(
            revenue_record_id=r.id,
            reason="already_resolved",
            risk_status=RiskStatus.low,
            priority=RecoveryPriority.low,
            current_state=RecoveryCaseState.recovered,
        )
        db.add(c)
        db.commit()

        result = RecoveryOrchestrator.orchestrate_recovery(db=db, case_id=c.id, auto_execute_low_risk=True)

        return DemoScenarioRunResponse(
            scenario_id="blocked",
            scenario_name="Policy-Blocked Terminal Case",
            payment_id=p.id,
            case_id=c.id,
            approval_id=None,
            case_state=c.current_state.value,
            message="Case has zero recoverable balance / terminal state. Policy engine blocked AI recommendation.",
            details={"policy_decision": "blocked", "orchestration_status": result.status.value},
        )

    elif scenario_id == "multi_channel":
        # 6. Fire multi-channel seed
        seed_resp = generate_synthetic_dataset(db, count=12, seed=seed, reset=False)
        return DemoScenarioRunResponse(
            scenario_id="multi_channel",
            scenario_name="Multi-Channel Dispatch Fleet",
            payment_id=0,
            case_id=0,
            case_state="active",
            message=f"Dispatched multi-channel recovery workflows across Email, SMS, WhatsApp, and Webhook. Created {seed_resp.cases_created} cases.",
            details={"cases_created": seed_resp.cases_created, "jobs_created": seed_resp.jobs_created},
        )

    elif scenario_id == "high_volume":
        # 7. High volume 50 items
        seed_resp = generate_synthetic_dataset(db, count=50, seed=seed, reset=False)
        return DemoScenarioRunResponse(
            scenario_id="high_volume",
            scenario_name="High-Volume Dashboard Dataset",
            payment_id=0,
            case_id=0,
            case_state="active",
            message=seed_resp.message,
            details={"cases_created": seed_resp.cases_created, "total_recoverable": seed_resp.total_recoverable_amount},
        )

    else:
        # Default scenario: fallback to success
        return run_scenario(db, "success", seed=seed)
