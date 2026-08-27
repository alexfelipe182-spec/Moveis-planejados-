"""add suppliers materials and project costs

Revision ID: 009_materials_production_costs
Revises: 008_project_quote_link
"""

import sqlalchemy as sa
from alembic import op

revision = "009_materials_production_costs"
down_revision = "008_project_quote_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("contact_name", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"])
    op.create_index("ix_suppliers_is_active", "suppliers", ["is_active"])

    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False, server_default="un"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("waste_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_materials_supplier_id", "materials", ["supplier_id"])
    op.create_index("ix_materials_name", "materials", ["name"])
    op.create_index("ix_materials_kind", "materials", ["kind"])
    op.create_index("ix_materials_is_active", "materials", ["is_active"])

    op.create_table(
        "project_costs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_project_costs_project_id", "project_costs", ["project_id"])
    op.create_index("ix_project_costs_material_id", "project_costs", ["material_id"])
    op.create_index("ix_project_costs_category", "project_costs", ["category"])


def downgrade() -> None:
    op.drop_table("project_costs")
    op.drop_table("materials")
    op.drop_table("suppliers")
