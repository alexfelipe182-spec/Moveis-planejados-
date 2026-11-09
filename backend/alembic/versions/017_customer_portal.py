"""customer portal accounts and messages

Revision ID: 017_customer_portal
Revises: 016_ai_automation
"""

from alembic import op
import sqlalchemy as sa


revision = "017_customer_portal"
down_revision = "016_ai_automation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_portal_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("invitation_token_hash", sa.String(length=64), nullable=True),
        sa.Column("invitation_expires_at", sa.DateTime(), nullable=True),
        sa.Column("reset_token_hash", sa.String(length=64), nullable=True),
        sa.Column("reset_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_token_hash"),
        sa.UniqueConstraint("reset_token_hash"),
        sa.UniqueConstraint("tenant_id", "customer_id", name="uq_customer_portal_customer"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_customer_portal_email"),
    )
    op.create_index(op.f("ix_customer_portal_accounts_customer_id"), "customer_portal_accounts", ["customer_id"])
    op.create_index(op.f("ix_customer_portal_accounts_email"), "customer_portal_accounts", ["email"])
    op.create_index(op.f("ix_customer_portal_accounts_tenant_id"), "customer_portal_accounts", ["tenant_id"])

    op.create_table(
        "customer_portal_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("author_type", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("author_type IN ('customer', 'staff')", name="ck_customer_portal_message_author"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_portal_messages_created_at"), "customer_portal_messages", ["created_at"])
    op.create_index(op.f("ix_customer_portal_messages_customer_id"), "customer_portal_messages", ["customer_id"])
    op.create_index(op.f("ix_customer_portal_messages_project_id"), "customer_portal_messages", ["project_id"])
    op.create_index(op.f("ix_customer_portal_messages_quote_id"), "customer_portal_messages", ["quote_id"])
    op.create_index(op.f("ix_customer_portal_messages_tenant_id"), "customer_portal_messages", ["tenant_id"])


def downgrade():
    op.drop_index(op.f("ix_customer_portal_messages_tenant_id"), table_name="customer_portal_messages")
    op.drop_index(op.f("ix_customer_portal_messages_quote_id"), table_name="customer_portal_messages")
    op.drop_index(op.f("ix_customer_portal_messages_project_id"), table_name="customer_portal_messages")
    op.drop_index(op.f("ix_customer_portal_messages_customer_id"), table_name="customer_portal_messages")
    op.drop_index(op.f("ix_customer_portal_messages_created_at"), table_name="customer_portal_messages")
    op.drop_table("customer_portal_messages")
    op.drop_index(op.f("ix_customer_portal_accounts_tenant_id"), table_name="customer_portal_accounts")
    op.drop_index(op.f("ix_customer_portal_accounts_email"), table_name="customer_portal_accounts")
    op.drop_index(op.f("ix_customer_portal_accounts_customer_id"), table_name="customer_portal_accounts")
    op.drop_table("customer_portal_accounts")
