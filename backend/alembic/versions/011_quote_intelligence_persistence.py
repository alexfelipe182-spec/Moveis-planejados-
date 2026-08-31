"""persist tenant-safe quote intelligence recommendations

Revision ID: 011_quote_intelligence
Revises: 010_bootstrap_admin
"""

import sqlalchemy as sa
from alembic import op

revision = "011_quote_intelligence"
down_revision = "010_bootstrap_admin"
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
    for column in (
        "intelligence_analyzed_at",
        "intelligence_sample_size",
        "intelligence_confidence",
        "risk_level",
        "risk_score",
        "recommended_total",
        "recommended_profit_margin",
    ):
        op.drop_column("quotes", column)

