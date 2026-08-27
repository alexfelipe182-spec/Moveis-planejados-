"""Link projects to their source quote.

Revision ID: 008_project_quote_link
Revises: 007_align_model_indexes
"""

import sqlalchemy as sa
from alembic import op

revision = "008_project_quote_link"
down_revision = "007_align_model_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("quote_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_projects_quote_id_quotes",
        "projects",
        "quotes",
        ["quote_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_projects_quote_id", "projects", ["quote_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_projects_quote_id", table_name="projects")
    op.drop_constraint("fk_projects_quote_id_quotes", "projects", type_="foreignkey")
    op.drop_column("projects", "quote_id")
