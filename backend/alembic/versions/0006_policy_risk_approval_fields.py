"""Add configurable high/critical risk approval fields to merchant_policies

Revision ID: 0006_policy_risk_approval_fields
Revises: 0005_merchant_policy_schema
Create Date: 2026-08-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_policy_risk_approval_fields"
down_revision: Union[str, None] = "0005_merchant_policy_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "merchant_policies",
        sa.Column(
            "require_approval_for_high_risk",
            sa.Boolean(),
            nullable=False,
            server_default="1",
            comment="Whether high-risk cases strictly require human approval before execution",
        ),
    )
    op.add_column(
        "merchant_policies",
        sa.Column(
            "require_approval_for_critical_risk",
            sa.Boolean(),
            nullable=False,
            server_default="1",
            comment="Whether critical-risk cases strictly require human approval before execution",
        ),
    )


def downgrade() -> None:
    op.drop_column("merchant_policies", "require_approval_for_critical_risk")
    op.drop_column("merchant_policies", "require_approval_for_high_risk")
