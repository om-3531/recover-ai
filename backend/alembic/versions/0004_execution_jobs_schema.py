"""Execution jobs schema

Revision ID: 0004_execution_jobs_schema
Revises: 0003_recovery_approval_schema
Create Date: 2026-08-24 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_execution_jobs_schema"
down_revision: Union[str, None] = "0003_recovery_approval_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recovery_execution_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recovery_case_id", sa.Integer(), nullable=False),
        sa.Column("recovery_approval_id", sa.Integer(), nullable=False),
        sa.Column("recovery_action_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "retry_scheduled",
                "cancelled",
                name="jobstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["recovery_case_id"],
            ["recovery_cases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_approval_id"],
            ["recovery_approvals.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_action_id"],
            ["recovery_actions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recovery_execution_jobs_id"), "recovery_execution_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_recovery_execution_jobs_recovery_case_id"), "recovery_execution_jobs", ["recovery_case_id"], unique=False)
    op.create_index(op.f("ix_recovery_execution_jobs_recovery_approval_id"), "recovery_execution_jobs", ["recovery_approval_id"], unique=False)
    op.create_index(op.f("ix_recovery_execution_jobs_recovery_action_id"), "recovery_execution_jobs", ["recovery_action_id"], unique=False)
    op.create_index(op.f("ix_recovery_execution_jobs_status"), "recovery_execution_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_recovery_execution_jobs_idempotency_key"), "recovery_execution_jobs", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_recovery_execution_jobs_idempotency_key"), table_name="recovery_execution_jobs")
    op.drop_index(op.f("ix_recovery_execution_jobs_status"), table_name="recovery_execution_jobs")
    op.drop_index(op.f("ix_recovery_execution_jobs_recovery_action_id"), table_name="recovery_execution_jobs")
    op.drop_index(op.f("ix_recovery_execution_jobs_recovery_approval_id"), table_name="recovery_execution_jobs")
    op.drop_index(op.f("ix_recovery_execution_jobs_recovery_case_id"), table_name="recovery_execution_jobs")
    op.drop_index(op.f("ix_recovery_execution_jobs_id"), table_name="recovery_execution_jobs")
    op.drop_table("recovery_execution_jobs")
