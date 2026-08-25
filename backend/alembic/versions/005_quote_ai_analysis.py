"""persist quote AI analysis

Revision ID: 005_quote_ai_analysis
Revises: 004_smart_quote_pricing
"""

import sqlalchemy as sa
from alembic import op

revision = "005_quote_ai_analysis"
down_revision = "004_smart_quote_pricing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quotes", sa.Column("ai_analysis", sa.Text(), nullable=True))
    op.add_column("quotes", sa.Column("ai_analyzed_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("quotes", "ai_analyzed_at")
    op.drop_column("quotes", "ai_analysis")
