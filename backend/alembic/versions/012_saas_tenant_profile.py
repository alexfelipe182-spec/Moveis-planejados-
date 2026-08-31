"""add SaaS tenant profile fields

Revision ID: 012_saas_tenant_profile
Revises: 011_multitenant_foundation
"""

import sqlalchemy as sa
from alembic import op

revision = "012_saas_tenant_profile"
down_revision = "011_multitenant_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "plan_code",
            sa.String(length=40),
            nullable=False,
            server_default="starter",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "updated_at")
    op.drop_column("tenants", "plan_code")
