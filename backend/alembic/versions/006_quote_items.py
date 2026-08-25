"""add quote items

Revision ID: 006_quote_items
Revises: 005_quote_ai_analysis
"""

import sqlalchemy as sa
from alembic import op

revision = "006_quote_items"
down_revision = "005_quote_ai_analysis"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quote_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("width", sa.Numeric(10, 2), nullable=True),
        sa.Column("height", sa.Numeric(10, 2), nullable=True),
        sa.Column("depth", sa.Numeric(10, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_quote_items_quote_id", "quote_items", ["quote_id"])


def downgrade():
    op.drop_index("ix_quote_items_quote_id", table_name="quote_items")
    op.drop_table("quote_items")
