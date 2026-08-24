"""Initial system health check table

Revision ID: 0001_initial_system_health
Revises: None
Create Date: 2026-08-24 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_system_health"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_health_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_system_health_checks_id"), "system_health_checks", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_system_health_checks_id"), table_name="system_health_checks")
    op.drop_table("system_health_checks")
