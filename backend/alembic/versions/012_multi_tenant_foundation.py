"""add organization ownership to every operational record

Revision ID: 012_multi_tenant
Revises: 011_quote_intelligence
"""

import sqlalchemy as sa
from alembic import op

revision = "012_multi_tenant"
down_revision = "011_quote_intelligence"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "users",
    "activities",
    "categories",
    "customers",
    "products",
    "quotes",
    "quote_items",
    "projects",
    "suppliers",
    "materials",
    "project_costs",
)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_status", "organizations", ["status"], unique=False)
    op.bulk_insert(
        sa.table(
            "organizations",
            sa.column("id", sa.Integer()),
            sa.column("name", sa.String()),
            sa.column("slug", sa.String()),
            sa.column("status", sa.String()),
        ),
        [{"id": 1, "name": "Multi-Marcenarias Legado", "slug": "legado", "status": "active"}],
    )

    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET organization_id = 1 WHERE organization_id IS NULL"))
        op.alter_column(table, "organization_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(
            f"fk_{table}_organization_id",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="RESTRICT" if table == "users" else "CASCADE",
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"], unique=False)

    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=False)
    op.create_unique_constraint("uq_categories_org_name", "categories", ["organization_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_categories_org_name", "categories", type_="unique")
    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)
    for table in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization_id", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
