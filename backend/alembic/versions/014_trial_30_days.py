"""start 30-day free trials for existing tenants

Revision ID: 014_trial_30_days
Revises: 013_commercial_saas
"""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op

revision = "014_trial_30_days"
down_revision = "013_commercial_saas"
branch_labels = None
depends_on = None

TRIAL_DAYS = 30


def upgrade():
    connection = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    trial_end = now + timedelta(days=TRIAL_DAYS)

    connection.execute(
        sa.text(
            """
            INSERT INTO subscriptions (
                tenant_id,
                provider,
                plan_code,
                status,
                trial_end,
                cancel_at_period_end,
                created_at,
                updated_at
            )
            SELECT
                tenants.id,
                'manual',
                tenants.plan_code,
                'trialing',
                :trial_end,
                false,
                :now,
                :now
            FROM tenants
            WHERE NOT EXISTS (
                SELECT 1
                FROM subscriptions
                WHERE subscriptions.tenant_id = tenants.id
            )
            """
        ),
        {"now": now, "trial_end": trial_end},
    )

    connection.execute(
        sa.text(
            """
            UPDATE subscriptions
            SET trial_end = :trial_end,
                updated_at = :now
            WHERE status = 'trialing'
              AND trial_end IS NULL
            """
        ),
        {"now": now, "trial_end": trial_end},
    )


def downgrade():
    # Data-only migration: keep subscription history intact on downgrade.
    pass
