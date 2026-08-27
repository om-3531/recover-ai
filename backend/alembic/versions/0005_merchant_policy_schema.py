"""Merchant policy schema

Revision ID: 0005_merchant_policy_schema
Revises: 0004_execution_jobs_schema
Create Date: 2026-08-25 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_merchant_policy_schema"
down_revision: Union[str, None] = "0004_execution_jobs_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "merchant_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("high_risk_threshold_paise", sa.Integer(), nullable=False, server_default="1000000"),
        sa.Column("critical_risk_threshold_paise", sa.Integer(), nullable=False, server_default="5000000"),
        sa.Column("human_review_threshold_paise", sa.Integer(), nullable=False, server_default="1000000"),
        sa.Column("auto_execute_low_risk", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("backoff_base_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("allowed_channels", sa.JSON(), nullable=False),
        sa.Column("preferred_channel", sa.String(length=32), nullable=False, server_default="email"),
        sa.Column("min_recovery_amount_paise", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column("max_recovery_amount_paise", sa.Integer(), nullable=False, server_default="100000000"),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_merchant_policies_id"), "merchant_policies", ["id"], unique=False)
    op.create_index(op.f("ix_merchant_policies_merchant_id"), "merchant_policies", ["merchant_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_merchant_policies_merchant_id"), table_name="merchant_policies")
    op.drop_index(op.f("ix_merchant_policies_id"), table_name="merchant_policies")
    op.drop_table("merchant_policies")
