"""commercial SaaS subscriptions and usage

Revision ID: 013_commercial_saas
Revises: 012_saas_tenant_profile
"""

from alembic import op
import sqlalchemy as sa

revision = "013_commercial_saas"
down_revision = "012_saas_tenant_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("provider_customer_id", sa.String(length=180), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=180), nullable=True),
        sa.Column("plan_code", sa.String(length=40), nullable=False, server_default="starter"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="trialing"),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("trial_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_subscriptions_tenant_id"),
        sa.UniqueConstraint("provider_customer_id", name="uq_subscriptions_provider_customer_id"),
        sa.UniqueConstraint("provider_subscription_id", name="uq_subscriptions_provider_subscription_id"),
    )
    op.create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(length=80), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "metric", "period", name="uq_usage_tenant_metric_period"),
    )
    op.create_index("ix_usage_counters_tenant_id", "usage_counters", ["tenant_id"])
    op.create_index("ix_usage_counters_period", "usage_counters", ["period"])


def downgrade():
    op.drop_index("ix_usage_counters_period", table_name="usage_counters")
    op.drop_index("ix_usage_counters_tenant_id", table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_tenant_id", table_name="subscriptions")
    op.drop_table("subscriptions")
