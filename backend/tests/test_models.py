"""
Tests for RecoverAI SQLAlchemy models, relationships, and constraints.

Covers:
1. Model imports & registration in Base.metadata
2. Payment -> PaymentEvent (1:N)
3. Payment -> RevenueRecord (1:1)
4. RevenueRecord -> RecoveryCase (1:N)
5. RecoveryCase -> RecoveryAction (1:N)
6. Generic AuditLog creation and metadata column mapping
7. Unique constraints (razorpay_payment_id, razorpay_event_id, payment_id on RevenueRecord)
8. Integer amount precision (paise)
9. End-to-end recovery lifecycle entity persistence
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models import (
    AuditLog,
    Payment,
    PaymentEvent,
    PaymentEventProcessingStatus,
    PaymentMethod,
    PaymentStatus,
    RecoveryAction,
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCase,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueRecord,
    RevenueStatus,
    RiskStatus,
    SystemHealthCheck,
)


def test_models_import_and_metadata_registration():
    """Verify all domain models are registered in Base.metadata."""
    table_names = Base.metadata.tables.keys()
    expected_tables = {
        "system_health_checks",
        "payments",
        "payment_events",
        "revenue_records",
        "recovery_cases",
        "recovery_actions",
        "audit_logs",
    }
    for expected in expected_tables:
        assert expected in table_names, f"Expected table '{expected}' in Base.metadata"


def test_payment_creation_and_fields(db_session):
    """Verify Payment model creates successfully with default and integer amounts."""
    payment = Payment(
        razorpay_payment_id="pay_test_001",
        razorpay_order_id="order_test_001",
        amount=50000,  # 500.00 INR in paise
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.card,
        customer_email="merchant_customer@example.com",
        customer_reference="cust_ref_123",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    assert payment.id is not None
    assert payment.razorpay_payment_id == "pay_test_001"
    assert payment.amount == 50000
    assert isinstance(payment.amount, int)
    assert payment.currency == "INR"
    assert payment.status == PaymentStatus.failed
    assert payment.method == PaymentMethod.card
    assert payment.created_at is not None
    assert payment.updated_at is not None


def test_payment_unique_razorpay_payment_id(db_session):
    """Enforce uniqueness of razorpay_payment_id."""
    p1 = Payment(
        razorpay_payment_id="pay_dup_001",
        amount=10000,
        currency="INR",
    )
    db_session.add(p1)
    db_session.commit()

    p2 = Payment(
        razorpay_payment_id="pay_dup_001",
        amount=20000,
        currency="INR",
    )
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_payment_to_payment_events_relationship(db_session):
    """Verify 1:N relationship from Payment to PaymentEvent with cascades."""
    payment = Payment(
        razorpay_payment_id="pay_event_rel_001",
        amount=75000,
        currency="INR",
        status=PaymentStatus.created,
    )
    db_session.add(payment)
    db_session.commit()

    event1 = PaymentEvent(
        payment_id=payment.id,
        razorpay_event_id="evt_001",
        event_type="payment.created",
        payload={"event": "payment.created", "id": "pay_event_rel_001"},
        processing_status=PaymentEventProcessingStatus.processed,
    )
    event2 = PaymentEvent(
        payment_id=payment.id,
        razorpay_event_id="evt_002",
        event_type="payment.failed",
        payload={"event": "payment.failed", "error_code": "BAD_REQUEST_ERROR"},
        processing_status=PaymentEventProcessingStatus.processed,
    )
    db_session.add_all([event1, event2])
    db_session.commit()
    db_session.refresh(payment)

    assert len(payment.events) == 2
    assert payment.events[0].razorpay_event_id == "evt_001"
    assert payment.events[1].event_type == "payment.failed"
    assert event1.payment.razorpay_payment_id == "pay_event_rel_001"


def test_payment_event_uniqueness_for_idempotency(db_session):
    """Verify duplicate webhook event IDs are rejected."""
    event1 = PaymentEvent(
        razorpay_event_id="evt_unique_123",
        event_type="payment.failed",
        payload={"data": 1},
    )
    db_session.add(event1)
    db_session.commit()

    event2 = PaymentEvent(
        razorpay_event_id="evt_unique_123",
        event_type="payment.failed",
        payload={"data": 2},
    )
    db_session.add(event2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_payment_to_revenue_record_one_to_one(db_session):
    """Verify 1:1 relationship between Payment and RevenueRecord."""
    payment = Payment(
        razorpay_payment_id="pay_rev_1to1_001",
        amount=150000,
        currency="INR",
        status=PaymentStatus.failed,
    )
    db_session.add(payment)
    db_session.commit()

    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=150000,
        recoverable_amount=150000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.commit()
    db_session.refresh(payment)
    db_session.refresh(revenue)

    assert payment.revenue_record is not None
    assert payment.revenue_record.id == revenue.id
    assert revenue.payment.razorpay_payment_id == "pay_rev_1to1_001"
    assert revenue.recoverable_amount == 150000


def test_revenue_record_unique_payment_id(db_session):
    """Enforce that one Payment cannot have multiple RevenueRecords."""
    payment = Payment(
        razorpay_payment_id="pay_rev_dup_001",
        amount=9900,
        currency="INR",
    )
    db_session.add(payment)
    db_session.commit()

    rev1 = RevenueRecord(
        payment_id=payment.id,
        gross_amount=9900,
        recoverable_amount=9900,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(rev1)
    db_session.commit()

    rev2 = RevenueRecord(
        payment_id=payment.id,
        gross_amount=9900,
        recoverable_amount=9900,
        currency="INR",
        status=RevenueStatus.lost,
    )
    db_session.add(rev2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_revenue_record_to_recovery_cases(db_session):
    """Verify 1:N relationship between RevenueRecord and RecoveryCase."""
    payment = Payment(
        razorpay_payment_id="pay_case_rel_001",
        amount=250000,
        currency="INR",
        status=PaymentStatus.failed,
    )
    db_session.add(payment)
    db_session.commit()

    rev = RevenueRecord(
        payment_id=payment.id,
        gross_amount=250000,
        recoverable_amount=250000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(rev)
    db_session.commit()

    case1 = RecoveryCase(
        revenue_record_id=rev.id,
        reason="insufficient_funds",
        risk_status=RiskStatus.high,
        priority=RecoveryPriority.high,
        current_state=RecoveryCaseState.open,
    )
    case2 = RecoveryCase(
        revenue_record_id=rev.id,
        reason="retry_attempt_2",
        risk_status=RiskStatus.critical,
        priority=RecoveryPriority.urgent,
        current_state=RecoveryCaseState.investigating,
    )
    db_session.add_all([case1, case2])
    db_session.commit()
    db_session.refresh(rev)

    assert len(rev.recovery_cases) == 2
    assert rev.recovery_cases[0].reason == "insufficient_funds"
    assert rev.recovery_cases[1].priority == RecoveryPriority.urgent
    assert case1.revenue_record.id == rev.id


def test_recovery_case_to_recovery_actions(db_session):
    """Verify 1:N relationship between RecoveryCase and RecoveryAction."""
    payment = Payment(
        razorpay_payment_id="pay_action_rel_001",
        amount=120000,
        currency="INR",
    )
    db_session.add(payment)
    db_session.commit()

    rev = RevenueRecord(
        payment_id=payment.id,
        gross_amount=120000,
        recoverable_amount=120000,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(rev)
    db_session.commit()

    case = RecoveryCase(
        revenue_record_id=rev.id,
        reason="card_expired",
        risk_status=RiskStatus.medium,
        priority=RecoveryPriority.medium,
        current_state=RecoveryCaseState.action_pending,
    )
    db_session.add(case)
    db_session.commit()

    action1 = RecoveryAction(
        recovery_case_id=case.id,
        action_type=RecoveryActionType.email_reminder,
        channel=RecoveryActionChannel.email,
        status=RecoveryActionStatus.scheduled,
        scheduled_at=datetime.now(timezone.utc),
    )
    action2 = RecoveryAction(
        recovery_case_id=case.id,
        action_type=RecoveryActionType.payment_link,
        channel=RecoveryActionChannel.sms,
        status=RecoveryActionStatus.executed,
        executed_at=datetime.now(timezone.utc),
        result={"link_id": "plink_test_123", "status": "sent"},
    )
    db_session.add_all([action1, action2])
    db_session.commit()
    db_session.refresh(case)

    assert len(case.actions) == 2
    assert case.actions[0].action_type == RecoveryActionType.email_reminder
    assert case.actions[1].result["link_id"] == "plink_test_123"
    assert action1.recovery_case.id == case.id


def test_audit_log_creation_and_metadata_mapping(db_session):
    """
    Verify generic AuditLog creation, non-colliding event_metadata mapping,
    and composite entity index.
    """
    audit = AuditLog(
        entity_type="recovery_case",
        entity_id="101",
        action="state_transition",
        actor="policy_engine",
        event_metadata={"from_state": "open", "to_state": "action_pending"},
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    assert audit.id is not None
    assert audit.entity_type == "recovery_case"
    assert audit.entity_id == "101"
    assert audit.action == "state_transition"
    assert audit.actor == "policy_engine"
    assert audit.event_metadata["to_state"] == "action_pending"
    assert audit.timestamp is not None

    # Check composite index exists on table
    table = Base.metadata.tables["audit_logs"]
    index_names = [idx.name for idx in table.indexes]
    assert "ix_audit_logs_entity_type_entity_id" in index_names


def test_full_recovery_flow_integration(db_session):
    """
    Verify full target business flow:
    Payment -> PaymentEvent -> RevenueRecord -> RecoveryCase -> RecoveryAction -> AuditLog
    """
    # 1. Razorpay Payment
    payment = Payment(
        razorpay_payment_id="pay_flow_full_001",
        razorpay_order_id="order_flow_001",
        amount=349900,  # 3,499.00 INR
        currency="INR",
        status=PaymentStatus.failed,
        method=PaymentMethod.upi,
        customer_email="subscriber@example.com",
    )
    db_session.add(payment)
    db_session.commit()

    # 2. Payment Event
    event = PaymentEvent(
        payment_id=payment.id,
        razorpay_event_id="evt_flow_001",
        event_type="payment.failed",
        payload={
            "id": "pay_flow_full_001",
            "error_code": "GATEWAY_TIMEOUT",
            "error_description": "Issuer bank timed out",
        },
        processing_status=PaymentEventProcessingStatus.processed,
    )
    db_session.add(event)

    # 3. Revenue Record (Revenue-at-Risk)
    revenue = RevenueRecord(
        payment_id=payment.id,
        gross_amount=349900,
        recoverable_amount=349900,
        currency="INR",
        status=RevenueStatus.at_risk,
    )
    db_session.add(revenue)
    db_session.commit()

    # 4. Recovery Case
    recovery_case = RecoveryCase(
        revenue_record_id=revenue.id,
        reason="GATEWAY_TIMEOUT",
        risk_status=RiskStatus.high,
        priority=RecoveryPriority.high,
        current_state=RecoveryCaseState.open,
    )
    db_session.add(recovery_case)
    db_session.commit()

    # 5. Recovery Action
    action = RecoveryAction(
        recovery_case_id=recovery_case.id,
        action_type=RecoveryActionType.retry_payment,
        channel=RecoveryActionChannel.system,
        status=RecoveryActionStatus.scheduled,
        scheduled_at=datetime.now(timezone.utc),
    )
    db_session.add(action)

    # 6. Audit Log
    audit = AuditLog(
        entity_type="recovery_case",
        entity_id=str(recovery_case.id),
        action="case_created",
        actor="system",
        event_metadata={"reason": "GATEWAY_TIMEOUT", "amount": 349900},
    )
    db_session.add(audit)
    db_session.commit()

    # Assertions across the chain
    db_session.refresh(payment)
    assert len(payment.events) == 1
    assert payment.revenue_record.gross_amount == 349900
    assert len(payment.revenue_record.recovery_cases) == 1
    assert payment.revenue_record.recovery_cases[0].actions[0].action_type == RecoveryActionType.retry_payment
    assert audit.id is not None
