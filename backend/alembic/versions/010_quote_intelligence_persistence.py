"""persist quote intelligence recommendations

Revision ID: 010_quote_intelligence_persistence
Revises: 009_materials_production_costs
"""

import sqlalchemy as sa
from alembic import op

revision = "010_quote_intelligence_persistence"
down_revision = "009_materials_production_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("recommended_profit_margin", sa.Numeric(5, 2), nullable=True))
    op.add_column("quotes", sa.Column("recommended_total", sa.Numeric(12, 2), nullable=True))
    op.add_column("quotes", sa.Column("risk_score", sa.Integer(), nullable=True))
    op.add_column("quotes", sa.Column("risk_level", sa.String(length=20), nullable=True))
    op.add_column("quotes", sa.Column("intelligence_confidence", sa.String(length=20), nullable=True))
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
