"""add projects, richer quotes, activities and password reset

Revision ID: 003_projects_history_password_reset
Revises: 002_refresh_tokens
"""

import sqlalchemy as sa
from alembic import op

revision = "003_projects_history_password_reset"
down_revision = "002_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quotes", sa.Column("measurements", sa.String(2000), nullable=True))
    op.add_column("quotes", sa.Column("materials", sa.String(2000), nullable=True))
    op.add_column("quotes", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE quotes SET updated_at = created_at WHERE updated_at IS NULL")

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("measurements", sa.String(2000), nullable=True),
        sa.Column("materials", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="planning"),
        sa.Column("project_date", sa.Date(), nullable=True),
        sa.Column("photos", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_projects_customer_id", "projects", ["customer_id"])
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_activities_user_id", "activities", ["user_id"])
    op.create_index("ix_activities_action", "activities", ["action"])
    op.create_index("ix_activities_entity", "activities", ["entity"])
    op.create_index("ix_activities_entity_id", "activities", ["entity_id"])
    op.create_index("ix_activities_created_at", "activities", ["created_at"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)


def downgrade():
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    for name in ["ix_activities_created_at", "ix_activities_entity_id", "ix_activities_entity", "ix_activities_action", "ix_activities_user_id"]:
        op.drop_index(name, table_name="activities")
    op.drop_table("activities")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_index("ix_projects_customer_id", table_name="projects")
    op.drop_table("projects")
    op.drop_column("quotes", "updated_at")
    op.drop_column("quotes", "materials")
    op.drop_column("quotes", "measurements")
