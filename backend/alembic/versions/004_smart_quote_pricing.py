"""add smart quote pricing fields

Revision ID: 004_smart_quote_pricing
Revises: 003_projects_history_pw_reset
"""

import sqlalchemy as sa
from alembic import op

revision = "004_smart_quote_pricing"
down_revision = "003_projects_history_pw_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quotes", sa.Column("material_cost", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("quotes", sa.Column("hardware_cost", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("quotes", sa.Column("labor_cost", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("quotes", sa.Column("finishing_cost", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("quotes", sa.Column("profit_margin", sa.Numeric(5, 2), nullable=False, server_default="30"))
    op.add_column("quotes", sa.Column("suggested_total", sa.Numeric(12, 2), nullable=False, server_default="0"))


def downgrade():
    for column in ["suggested_total", "profit_margin", "finishing_cost", "labor_cost", "hardware_cost", "material_cost"]:
        op.drop_column("quotes", column)
