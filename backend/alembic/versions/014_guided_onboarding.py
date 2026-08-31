"""guided onboarding tenant profile

Revision ID: 014_guided_onboarding
Revises: 013_commercial_saas
"""

from alembic import op
import sqlalchemy as sa

revision = "014_guided_onboarding"
down_revision = "013_commercial_saas"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tenants", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("tenants", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("state", sa.String(length=40), nullable=True))
    op.add_column("tenants", sa.Column("document", sa.String(length=30), nullable=True))
    op.add_column("tenants", sa.Column("default_profit_margin", sa.Numeric(5, 2), nullable=False, server_default="30.00"))
    op.add_column("tenants", sa.Column("onboarding_step", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("tenants", sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tenants", sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("tenants", "onboarding_completed_at")
    op.drop_column("tenants", "onboarding_completed")
    op.drop_column("tenants", "onboarding_step")
    op.drop_column("tenants", "default_profit_margin")
    op.drop_column("tenants", "document")
    op.drop_column("tenants", "state")
    op.drop_column("tenants", "city")
    op.drop_column("tenants", "phone")
