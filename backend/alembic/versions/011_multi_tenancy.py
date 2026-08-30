"""introduce tenant isolation for SaaS

Revision ID: 011_multi_tenancy
Revises: 010_bootstrap_admin
"""

import sqlalchemy as sa
from alembic import op

revision = "011_multi_tenancy"
down_revision = "010_bootstrap_admin"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "users",
    "categories",
    "customers",
    "products",
    "quotes",
    "projects",
    "activities",
    "suppliers",
    "materials",
    "project_costs",
    "quote_items",
]


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="trialing"),
        sa.Column("plan_code", sa.String(30), nullable=False, server_default="starter"),
        sa.Column("billing_email", sa.String(320), nullable=True),
        sa.Column("billing_provider", sa.String(30), nullable=False, server_default="disabled"),
        sa.Column("external_customer_id", sa.String(255), nullable=True),
        sa.Column("external_subscription_id", sa.String(255), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("subscription_ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_status", "tenants", ["status"])
    op.create_index("ix_tenants_plan_code", "tenants", ["plan_code"])
    op.create_index("ix_tenants_external_customer_id", "tenants", ["external_customer_id"])
    op.create_index("ix_tenants_external_subscription_id", "tenants", ["external_subscription_id"])

    connection = op.get_bind()
    legacy_tenant_id = connection.execute(
        sa.text(
            """
            INSERT INTO tenants (
                name, slug, status, plan_code, billing_provider, created_at, updated_at
            ) VALUES (
                'Multi-Marcenarias — Operação Legada',
                'operacao-legada',
                'active',
                'business',
                'disabled',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            ) RETURNING id
            """
        )
    ).scalar_one()

    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))
        connection.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": legacy_tenant_id},
        )
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="RESTRICT" if table == "users" else "CASCADE",
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    op.add_column(
        "users",
        sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_users_is_superadmin", "users", ["is_superadmin"])

    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.create_unique_constraint(
        "uq_categories_tenant_name",
        "categories",
        ["tenant_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_categories_tenant_name", "categories", type_="unique")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])
    op.drop_index("ix_users_is_superadmin", table_name="users")
    op.drop_column("users", "is_superadmin")

    for table in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_column(table, "tenant_id")

    op.drop_table("tenants")
