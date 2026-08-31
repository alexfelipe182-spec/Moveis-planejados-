"""add plan catalog, subscriptions, webhook idempotency and platform role

Revision ID: 013_plans_platform
Revises: 012_multi_tenant
"""

import sqlalchemy as sa
from alembic import op

revision = "013_plans_platform"
down_revision = "012_multi_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_users_is_platform_admin", "users", ["is_platform_admin"], unique=False)
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)
    op.create_index("ix_plans_is_active", "plans", ["is_active"], unique=False)
    # Keep the seed literal so `alembic upgrade --sql` also works; JSON bind
    # values cannot be rendered by Alembic's offline PostgreSQL compiler.
    op.execute(sa.text(
        """
        INSERT INTO plans (id, code, name, monthly_price_cents, max_users, features, is_active)
        VALUES
          (1, 'starter', 'Starter', 0, 3, '{"quotes": true, "production": true}'::json, TRUE),
          (2, 'pro', 'Pro', 9900, 10, '{"quotes": true, "production": true, "intelligence": true}'::json, TRUE),
          (3, 'scale', 'Scale', 24900, 50, '{"quotes": true, "production": true, "intelligence": true, "platform_support": true}'::json, TRUE)
        """
    ))
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("provider", sa.String(30), nullable=False, server_default="sandbox"),
        sa.Column("provider_customer_id", sa.String(160)),
        sa.Column("provider_subscription_id", sa.String(160)),
        sa.Column("trial_end", sa.DateTime()),
        sa.Column("current_period_end", sa.DateTime()),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_subscriptions_organization"),
    )
    op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"], unique=False)
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"], unique=False)
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"], unique=False)
    op.create_index("ix_subscriptions_provider_customer_id", "subscriptions", ["provider_customer_id"], unique=False)
    op.create_index("ix_subscriptions_provider_subscription_id", "subscriptions", ["provider_subscription_id"], unique=False)
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("payload_hash", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "event_id", name="uq_billing_webhook_provider_event"),
    )
    op.create_index("ix_billing_webhook_events_event_id", "billing_webhook_events", ["event_id"], unique=False)
    op.execute(sa.text("INSERT INTO subscriptions (organization_id, plan_id, status, provider) SELECT id, 1, 'active', 'legacy' FROM organizations"))


def downgrade() -> None:
    op.drop_index("ix_billing_webhook_events_event_id", table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")
    for index in (
        "ix_subscriptions_provider_subscription_id",
        "ix_subscriptions_provider_customer_id",
        "ix_subscriptions_status",
        "ix_subscriptions_plan_id",
        "ix_subscriptions_organization_id",
    ):
        op.drop_index(index, table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_plans_is_active", table_name="plans")
    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_table("plans")
    op.drop_index("ix_users_is_platform_admin", table_name="users")
    op.drop_column("users", "is_platform_admin")
