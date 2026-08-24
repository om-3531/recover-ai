"""Recovery approval schema

Revision ID: 0003_recovery_approval_schema
Revises: 0002_payment_recovery_schema
Create Date: 2026-08-24 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_recovery_approval_schema"
down_revision: Union[str, None] = "0002_payment_recovery_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recovery_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recovery_case_id", sa.Integer(), nullable=False),
        sa.Column("recovery_action_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_id", sa.String(length=255), nullable=True),
        sa.Column(
            "action_type",
            sa.Enum(
                "payment_link",
                "email_reminder",
                "sms_reminder",
                "whatsapp_reminder",
                "retry_payment",
                "webhook_ping",
                "discount_offer",
                "custom",
                name="recoveryactiontype",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum(
                "email",
                "sms",
                "whatsapp",
                "webhook",
                "in_app",
                "system",
                name="recoveryactionchannel",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "expired",
                "cancelled",
                name="approvalstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("rejection_reason", sa.String(length=255), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["recovery_case_id"],
            ["recovery_cases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_action_id"],
            ["recovery_actions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recovery_approvals_id"), "recovery_approvals", ["id"], unique=False)
    op.create_index(op.f("ix_recovery_approvals_recovery_case_id"), "recovery_approvals", ["recovery_case_id"], unique=False)
    op.create_index(op.f("ix_recovery_approvals_recovery_action_id"), "recovery_approvals", ["recovery_action_id"], unique=False)
    op.create_index(op.f("ix_recovery_approvals_recommendation_id"), "recovery_approvals", ["recommendation_id"], unique=False)
    op.create_index(op.f("ix_recovery_approvals_action_type"), "recovery_approvals", ["action_type"], unique=False)
    op.create_index(op.f("ix_recovery_approvals_channel"), "recovery_approvals", ["channel"], unique=False)
    op.create_index(op.f("ix_recovery_approvals_status"), "recovery_approvals", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recovery_approvals_status"), table_name="recovery_approvals")
    op.drop_index(op.f("ix_recovery_approvals_channel"), table_name="recovery_approvals")
    op.drop_index(op.f("ix_recovery_approvals_action_type"), table_name="recovery_approvals")
    op.drop_index(op.f("ix_recovery_approvals_recommendation_id"), table_name="recovery_approvals")
    op.drop_index(op.f("ix_recovery_approvals_recovery_action_id"), table_name="recovery_approvals")
    op.drop_index(op.f("ix_recovery_approvals_recovery_case_id"), table_name="recovery_approvals")
    op.drop_index(op.f("ix_recovery_approvals_id"), table_name="recovery_approvals")
    op.drop_table("recovery_approvals")
