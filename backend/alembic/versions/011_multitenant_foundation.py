"""add tenant isolation foundation

Revision ID: 011_multitenant_foundation
Revises: 010_bootstrap_admin
"""

import sqlalchemy as sa
from alembic import op

revision = "011_multitenant_foundation"
down_revision = "010_bootstrap_admin"
branch_labels = None
depends_on = None

BUSINESS_TABLES = (
    "activities",
    "categories",
    "customers",
    "materials",
    "products",
    "project_costs",
    "projects",
    "quote_items",
    "quotes",
    "suppliers",
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_tenants_name", "tenants", ["name"])
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    connection = op.get_bind()
    tenant_id = connection.execute(
        sa.text(
            """
            INSERT INTO tenants (name, slug, is_active)
            VALUES ('Multi-Marcenarias — Base existente', 'legacy-default', TRUE)
            RETURNING id
            """
        )
    ).scalar_one()

    op.add_column("users", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_foreign_key(
        "fk_users_tenant_id_tenants",
        "users",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="SET NULL",
    )
    connection.execute(sa.text("UPDATE users SET tenant_id = :tenant_id"), {"tenant_id": tenant_id})

    for table in BUSINESS_TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant_id_tenants",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )
        connection.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        op.alter_column(table, "tenant_id", nullable=False)

    # Revision 007 created a globally-unique index on category name. In a
    # multi-tenant system the same category name must be allowed in different
    # marcenarias, while remaining unique within each tenant.
    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=False)
    op.create_unique_constraint(
        "uq_categories_tenant_name",
        "categories",
        ["tenant_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_categories_tenant_name", "categories", type_="unique")
    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)

    for table in reversed(BUSINESS_TABLES):
        op.drop_constraint(f"fk_{table}_tenant_id_tenants", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    op.drop_constraint("fk_users_tenant_id_tenants", "users", type_="foreignkey")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_column("users", "tenant_id")

    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_index("ix_tenants_name", table_name="tenants")
    op.drop_table("tenants")
