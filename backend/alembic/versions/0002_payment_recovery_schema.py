"""Payment and recovery schema

Revision ID: 0002_payment_recovery_schema
Revises: 0001_initial_system_health
Create Date: 2026-08-24 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_payment_recovery_schema"
down_revision: Union[str, None] = "0001_initial_system_health"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. payments
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(length=255), nullable=False),
        sa.Column("razorpay_order_id", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False, comment="Amount in paise (e.g. 50000 = 500.00 INR)"),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column(
            "status",
            sa.Enum("created", "authorized", "captured", "failed", "refunded", name="paymentstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.Enum("card", "upi", "netbanking", "wallet", "emi", "other", name="paymentmethod", native_enum=False, length=32),
            nullable=True,
        ),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("customer_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_id"), "payments", ["id"], unique=False)
    op.create_index(op.f("ix_payments_razorpay_payment_id"), "payments", ["razorpay_payment_id"], unique=True)
    op.create_index(op.f("ix_payments_razorpay_order_id"), "payments", ["razorpay_order_id"], unique=False)
    op.create_index(op.f("ix_payments_status"), "payments", ["status"], unique=False)
    op.create_index(op.f("ix_payments_customer_reference"), "payments", ["customer_reference"], unique=False)

    # 2. payment_events
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("razorpay_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "processing_status",
            sa.Enum("pending", "processed", "failed", name="paymenteventprocessingstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_events_id"), "payment_events", ["id"], unique=False)
    op.create_index(op.f("ix_payment_events_payment_id"), "payment_events", ["payment_id"], unique=False)
    op.create_index(op.f("ix_payment_events_razorpay_event_id"), "payment_events", ["razorpay_event_id"], unique=True)
    op.create_index(op.f("ix_payment_events_event_type"), "payment_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_payment_events_processing_status"), "payment_events", ["processing_status"], unique=False)

    # 3. revenue_records
    op.create_table(
        "revenue_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("gross_amount", sa.Integer(), nullable=False, comment="Gross revenue amount in paise"),
        sa.Column("recoverable_amount", sa.Integer(), nullable=False, comment="Recoverable amount in paise"),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "recognized", "at_risk", "recovered", "lost", name="revenuestatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_revenue_records_id"), "revenue_records", ["id"], unique=False)
    op.create_index(op.f("ix_revenue_records_payment_id"), "revenue_records", ["payment_id"], unique=True)
    op.create_index(op.f("ix_revenue_records_status"), "revenue_records", ["status"], unique=False)

    # 4. recovery_cases
    op.create_table(
        "recovery_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revenue_record_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "risk_status",
            sa.Enum("low", "medium", "high", "critical", name="riskstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", "urgent", name="recoverypriority", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "current_state",
            sa.Enum("open", "investigating", "action_pending", "recovering", "recovered", "closed", "failed", name="recoverycasestate", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["revenue_record_id"], ["revenue_records.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recovery_cases_id"), "recovery_cases", ["id"], unique=False)
    op.create_index(op.f("ix_recovery_cases_revenue_record_id"), "recovery_cases", ["revenue_record_id"], unique=False)
    op.create_index(op.f("ix_recovery_cases_risk_status"), "recovery_cases", ["risk_status"], unique=False)
    op.create_index(op.f("ix_recovery_cases_priority"), "recovery_cases", ["priority"], unique=False)
    op.create_index(op.f("ix_recovery_cases_current_state"), "recovery_cases", ["current_state"], unique=False)

    # 5. recovery_actions
    op.create_table(
        "recovery_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recovery_case_id", sa.Integer(), nullable=False),
        sa.Column(
            "action_type",
            sa.Enum("payment_link", "email_reminder", "sms_reminder", "whatsapp_reminder", "retry_payment", "webhook_ping", "discount_offer", "custom", name="recoveryactiontype", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum("email", "sms", "whatsapp", "webhook", "in_app", "system", name="recoveryactionchannel", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "scheduled", "executed", "failed", "cancelled", name="recoveryactionstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recovery_actions_id"), "recovery_actions", ["id"], unique=False)
    op.create_index(op.f("ix_recovery_actions_recovery_case_id"), "recovery_actions", ["recovery_case_id"], unique=False)
    op.create_index(op.f("ix_recovery_actions_action_type"), "recovery_actions", ["action_type"], unique=False)
    op.create_index(op.f("ix_recovery_actions_channel"), "recovery_actions", ["channel"], unique=False)
    op.create_index(op.f("ix_recovery_actions_status"), "recovery_actions", ["status"], unique=False)

    # 6. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_timestamp"), "audit_logs", ["timestamp"], unique=False)
    op.create_index(
        "ix_audit_logs_entity_type_entity_id",
        "audit_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    # 6. audit_logs
    op.drop_index("ix_audit_logs_entity_type_entity_id", table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_timestamp"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    # 5. recovery_actions
    op.drop_index(op.f("ix_recovery_actions_status"), table_name="recovery_actions")
    op.drop_index(op.f("ix_recovery_actions_channel"), table_name="recovery_actions")
    op.drop_index(op.f("ix_recovery_actions_action_type"), table_name="recovery_actions")
    op.drop_index(op.f("ix_recovery_actions_recovery_case_id"), table_name="recovery_actions")
    op.drop_index(op.f("ix_recovery_actions_id"), table_name="recovery_actions")
    op.drop_table("recovery_actions")

    # 4. recovery_cases
    op.drop_index(op.f("ix_recovery_cases_current_state"), table_name="recovery_cases")
    op.drop_index(op.f("ix_recovery_cases_priority"), table_name="recovery_cases")
    op.drop_index(op.f("ix_recovery_cases_risk_status"), table_name="recovery_cases")
    op.drop_index(op.f("ix_recovery_cases_revenue_record_id"), table_name="recovery_cases")
    op.drop_index(op.f("ix_recovery_cases_id"), table_name="recovery_cases")
    op.drop_table("recovery_cases")

    # 3. revenue_records
    op.drop_index(op.f("ix_revenue_records_status"), table_name="revenue_records")
    op.drop_index(op.f("ix_revenue_records_payment_id"), table_name="revenue_records")
    op.drop_index(op.f("ix_revenue_records_id"), table_name="revenue_records")
    op.drop_table("revenue_records")

    # 2. payment_events
    op.drop_index(op.f("ix_payment_events_processing_status"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_event_type"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_razorpay_event_id"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_payment_id"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_id"), table_name="payment_events")
    op.drop_table("payment_events")

    # 1. payments
    op.drop_index(op.f("ix_payments_customer_reference"), table_name="payments")
    op.drop_index(op.f("ix_payments_status"), table_name="payments")
    op.drop_index(op.f("ix_payments_razorpay_order_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_razorpay_payment_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_id"), table_name="payments")
    op.drop_table("payments")
