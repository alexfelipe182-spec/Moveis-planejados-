"""start 30-day free trials for existing tenants

Revision ID: 015_trial_30_days
Revises: 014_guided_onboarding
"""

import sqlalchemy as sa
from alembic import op

revision = "015_trial_30_days"
down_revision = "014_guided_onboarding"
branch_labels = None
depends_on = None

def upgrade():
    # Evaluate dates when SQL is applied, not when a recovery file is exported.
    # UTC matches the application's timezone-naive timestamp convention.
    op.execute(
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
                (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + INTERVAL '30 days',
                false,
                CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
            FROM tenants
            WHERE NOT EXISTS (
                SELECT 1
                FROM subscriptions
                WHERE subscriptions.tenant_id = tenants.id
            )
            """
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE subscriptions
            SET trial_end = (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + INTERVAL '30 days',
                updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
            WHERE status = 'trialing'
              AND trial_end IS NULL
            """
        ),
    )


def downgrade():
    # Data-only migration: keep subscription history intact on downgrade.
    pass
