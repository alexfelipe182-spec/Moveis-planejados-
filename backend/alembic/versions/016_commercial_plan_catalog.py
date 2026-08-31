"""publish the initial commercial plan catalog

Revision ID: 016_commercial_plan_catalog
Revises: 015_tenant_reference_guards
"""

import sqlalchemy as sa
from alembic import op


revision = "016_commercial_plan_catalog"
down_revision = "015_tenant_reference_guards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        """
        UPDATE plans
        SET name = 'Essencial',
            monthly_price_cents = 4900,
            max_users = 3,
            features = '{"customers": true, "quotes": true, "projects": true, "production": true, "costs": true}'::json
        WHERE code = 'starter';

        UPDATE plans
        SET name = 'Profissional',
            monthly_price_cents = 9900,
            max_users = 10,
            features = '{"customers": true, "quotes": true, "projects": true, "production": true, "costs": true, "intelligence": true, "automation": true, "profitability": true}'::json
        WHERE code = 'pro';

        UPDATE plans
        SET name = 'Empresarial',
            monthly_price_cents = 24900,
            max_users = 50,
            features = '{"customers": true, "quotes": true, "projects": true, "production": true, "costs": true, "intelligence": true, "automation": true, "profitability": true, "advanced_reports": true, "priority_support": true, "assisted_onboarding": true}'::json
        WHERE code = 'scale';
        """
    ))


def downgrade() -> None:
    op.execute(sa.text(
        """
        UPDATE plans
        SET name = 'Starter', monthly_price_cents = 0, max_users = 3,
            features = '{"quotes": true, "production": true}'::json
        WHERE code = 'starter';

        UPDATE plans
        SET name = 'Pro', monthly_price_cents = 9900, max_users = 10,
            features = '{"quotes": true, "production": true, "intelligence": true}'::json
        WHERE code = 'pro';

        UPDATE plans
        SET name = 'Scale', monthly_price_cents = 24900, max_users = 50,
            features = '{"quotes": true, "production": true, "intelligence": true, "platform_support": true}'::json
        WHERE code = 'scale';
        """
    ))
