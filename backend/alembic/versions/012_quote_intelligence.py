"""persist predictive quote intelligence

Revision ID: 012_quote_intelligence
Revises: 011_multi_tenancy
"""

import sqlalchemy as sa
from alembic import op

revision = "012_quote_intelligence"
down_revision = "011_multi_tenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("recommended_profit_margin", sa.Numeric(5, 2), nullable=True))
    op.add_column("quotes", sa.Column("recommended_total", sa.Numeric(12, 2), nullable=True))
    op.add_column("quotes", sa.Column("risk_score", sa.Integer(), nullable=True))
    op.add_column("quotes", sa.Column("risk_level", sa.String(20), nullable=True))
    op.add_column("quotes", sa.Column("intelligence_confidence", sa.String(20), nullable=True))
    op.add_column("quotes", sa.Column("intelligence_sample_size", sa.Integer(), nullable=True))
    op.add_column("quotes", sa.Column("intelligence_analyzed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("quotes", "intelligence_analyzed_at")
    op.drop_column("quotes", "intelligence_sample_size")
    op.drop_column("quotes", "intelligence_confidence")
    op.drop_column("quotes", "risk_level")
    op.drop_column("quotes", "risk_score")
    op.drop_column("quotes", "recommended_total")
    op.drop_column("quotes", "recommended_profit_margin")
