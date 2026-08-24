"""
Unit tests for RecoverAI Service Layer.

Tests:
1. PaymentService (create, get, list, update status, duplicate conflict, audit)
2. RevenueService (create, 1:1 constraint, mark at-risk, audit)
3. RecoveryService (create case, state machine validation, invalid transition rejection, actions)
4. AuditService (create, query, filter)
"""

import pytest

from app.core.exceptions import ConflictError, InvalidStateTransitionError, NotFoundError
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
from app.schemas.payments import PaymentCreate
from app.schemas.recovery import (
    RecoveryActionCreate,
    RecoveryActionStatusUpdate,
    RecoveryCaseCreate,
    RecoveryCaseStateUpdate,
)
from app.schemas.revenue import RevenueRecordCreate, RevenueStatusUpdate
from app.services import (
    AuditService,
    PaymentService,
    RecoveryService,
    RevenueService,
)


def test_payment_service_create_and_get(db_session):
    """Verify PaymentService creates payment and audit log."""
    payment_in = PaymentCreate(
        razorpay_payment_id="pay_srv_001",
        razorpay_order_id="order_srv_001",
        amount=59900,  # 599.00 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
        customer_email="customer@example.com",
    )
    payment = PaymentService.create_payment(db_session, payment_in)

    assert payment.id is not None
    assert payment.amount == 59900
    assert payment.razorpay_payment_id == "pay_srv_001"

    # Verify audit log was created
    audits, total = AuditService.list_audit_logs(
        db_session, entity_type="payment", entity_id=str(payment.id)
    )
    assert total >= 1
    assert audits[0].action == "payment_created"

    # Get by ID and by Razorpay ID
    fetched_by_id = PaymentService.get_payment_by_id(db_session, payment.id)
    assert fetched_by_id.id == payment.id

    fetched_by_rzp = PaymentService.get_payment_by_razorpay_id(
        db_session, "pay_srv_001"
    )
    assert fetched_by_rzp.id == payment.id


def test_payment_service_duplicate_conflict(db_session):
    """Verify duplicate razorpay_payment_id raises ConflictError."""
    payment_in = PaymentCreate(
        razorpay_payment_id="pay_srv_dup",
        amount=10000,
    )
    PaymentService.create_payment(db_session, payment_in)

    with pytest.raises(ConflictError) as exc_info:
        PaymentService.create_payment(db_session, payment_in)
    assert "already exists" in str(exc_info.value.message)


def test_payment_service_not_found(db_session):
    """Verify non-existent payments raise NotFoundError."""
    with pytest.raises(NotFoundError):
        PaymentService.get_payment_by_id(db_session, 99999)

    with pytest.raises(NotFoundError):
        PaymentService.get_payment_by_razorpay_id(db_session, "non_existent_pay_id")


def test_payment_service_list_and_update_status(db_session):
    """Verify listing with status filter and status update with audit log."""
    p1 = PaymentService.create_payment(
        db_session,
        PaymentCreate(razorpay_payment_id="pay_list_1", amount=1000, status=PaymentStatus.failed),
    )
    PaymentService.create_payment(
        db_session,
        PaymentCreate(razorpay_payment_id="pay_list_2", amount=2000, status=PaymentStatus.captured),
    )

    items, total = PaymentService.list_payments(db_session, status=PaymentStatus.failed)
    assert total == 1
    assert items[0].razorpay_payment_id == "pay_list_1"

    updated = PaymentService.update_payment_status(
        db_session, p1.id, PaymentStatus.authorized
    )
    assert updated.status == PaymentStatus.authorized

    audits, _ = AuditService.list_audit_logs(
        db_session, entity_type="payment", entity_id=str(p1.id), action="payment_status_updated"
    )
    assert len(audits) == 1
    assert audits[0].event_metadata["from_status"] == "failed"
    assert audits[0].event_metadata["to_status"] == "authorized"


def test_revenue_service_create_and_1to1_conflict(db_session):
    """Verify RevenueService 1:1 constraints and amount inheritance."""
    payment = PaymentService.create_payment(
        db_session,
        PaymentCreate(razorpay_payment_id="pay_rev_srv_1", amount=45000),
    )

    rev_in = RevenueRecordCreate(
        payment_id=payment.id,
        status=RevenueStatus.at_risk,
    )
    rev = RevenueService.create_revenue_record(db_session, rev_in)

    assert rev.id is not None
    assert rev.gross_amount == 45000  # Defaulted from payment.amount
    assert rev.recoverable_amount == 45000  # Defaulted to gross_amount for at_risk
    assert rev.status == RevenueStatus.at_risk

    # Second revenue record for same payment must fail with ConflictError
    with pytest.raises(ConflictError):
        RevenueService.create_revenue_record(db_session, rev_in)


def test_revenue_service_mark_at_risk_and_update(db_session):
    """Verify marking revenue at-risk and updating status."""
    payment = PaymentService.create_payment(
        db_session,
        PaymentCreate(razorpay_payment_id="pay_rev_risk_1", amount=80000),
    )
    rev = RevenueService.create_revenue_record(
        db_session,
        RevenueRecordCreate(payment_id=payment.id, status=RevenueStatus.pending),
    )
    assert rev.recoverable_amount == 0

    marked = RevenueService.mark_revenue_at_risk(db_session, rev.id)
    assert marked.status == RevenueStatus.at_risk
    assert marked.recoverable_amount == 80000

    updated = RevenueService.update_revenue_status(
        db_session,
        rev.id,
        RevenueStatusUpdate(status=RevenueStatus.recovered, recoverable_amount=0),
    )
    assert updated.status == RevenueStatus.recovered
    assert updated.recoverable_amount == 0


def test_recovery_service_case_lifecycle_and_transitions(db_session):
    """Verify recovery case creation, actions, and state transitions."""
    payment = PaymentService.create_payment(
        db_session,
        PaymentCreate(razorpay_payment_id="pay_rec_srv_1", amount=120000),
    )
    rev = RevenueService.create_revenue_record(
        db_session,
        RevenueRecordCreate(payment_id=payment.id, status=RevenueStatus.at_risk),
    )

    case = RecoveryService.create_recovery_case(
        db_session,
        RecoveryCaseCreate(
            revenue_record_id=rev.id,
            reason="insufficient_funds",
            priority=RecoveryPriority.high,
        ),
    )
    assert case.current_state == RecoveryCaseState.open
    assert case.priority == RecoveryPriority.high

    # Valid transition: open -> action_pending
    updated_case = RecoveryService.update_recovery_case_state(
        db_session,
        case.id,
        RecoveryCaseStateUpdate(current_state=RecoveryCaseState.action_pending),
    )
    assert updated_case.current_state == RecoveryCaseState.action_pending

    # Valid transition: action_pending -> recovering
    updated_case = RecoveryService.update_recovery_case_state(
        db_session,
        case.id,
        RecoveryCaseStateUpdate(current_state=RecoveryCaseState.recovering),
    )
    assert updated_case.current_state == RecoveryCaseState.recovering

    # Valid transition: recovering -> closed
    updated_case = RecoveryService.update_recovery_case_state(
        db_session,
        case.id,
        RecoveryCaseStateUpdate(current_state=RecoveryCaseState.closed),
    )
    assert updated_case.current_state == RecoveryCaseState.closed

    # INVALID transition: closed -> recovering directly (must reopen to open first)
    with pytest.raises(InvalidStateTransitionError):
        RecoveryService.update_recovery_case_state(
            db_session,
            case.id,
            RecoveryCaseStateUpdate(current_state=RecoveryCaseState.recovering),
        )


def test_recovery_service_actions_management(db_session):
    """Verify creating and updating recovery actions on a case."""
    payment = PaymentService.create_payment(
        db_session,
        PaymentCreate(razorpay_payment_id="pay_act_srv_1", amount=99900),
    )
    rev = RevenueService.create_revenue_record(
        db_session,
        RevenueRecordCreate(payment_id=payment.id, status=RevenueStatus.at_risk),
    )
    case = RecoveryService.create_recovery_case(
        db_session,
        RecoveryCaseCreate(revenue_record_id=rev.id),
    )

    action = RecoveryService.create_recovery_action(
        db_session,
        case.id,
        RecoveryActionCreate(
            action_type=RecoveryActionType.payment_link,
            channel=RecoveryActionChannel.sms,
            status=RecoveryActionStatus.pending,
        ),
    )
    assert action.id is not None
    assert action.status == RecoveryActionStatus.pending

    updated_action = RecoveryService.update_recovery_action_status(
        db_session,
        action.id,
        RecoveryActionStatusUpdate(
            status=RecoveryActionStatus.executed,
            result={"status": "sent", "link_id": "plink_123"},
        ),
    )
    assert updated_action.status == RecoveryActionStatus.executed
    assert updated_action.executed_at is not None
    assert updated_action.result["link_id"] == "plink_123"

    # Verify case with actions preloaded
    fetched_case = RecoveryService.get_recovery_case_by_id(db_session, case.id)
    assert len(fetched_case.actions) == 1
    assert fetched_case.actions[0].id == action.id
