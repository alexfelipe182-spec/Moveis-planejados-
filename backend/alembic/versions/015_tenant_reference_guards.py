"""enforce same-tenant references at the database boundary

Application filters remain the primary read isolation mechanism.  These
composite keys close the second hole: a malformed import or direct SQL write
cannot connect a record from one marcenaria to a record owned by another.
"""

import sqlalchemy as sa
from alembic import op

revision = "015_tenant_reference_guards"
down_revision = "014_platform_admin_bootstrap"
branch_labels = None
depends_on = None


PARENT_KEYS = (
    ("users", "uq_users_org_id"),
    ("categories", "uq_categories_org_id"),
    ("customers", "uq_customers_org_id"),
    ("products", "uq_products_org_id"),
    ("quotes", "uq_quotes_org_id"),
    ("quote_items", "uq_quote_items_org_id"),
    ("projects", "uq_projects_org_id"),
    ("suppliers", "uq_suppliers_org_id"),
    ("materials", "uq_materials_org_id"),
    ("project_costs", "uq_project_costs_org_id"),
)


def upgrade() -> None:
    for table, constraint in PARENT_KEYS:
        op.create_unique_constraint(constraint, table, ["organization_id", "id"])

    constraints = (
        ("fk_products_category_tenant", "products", ["organization_id", "category_id"], "categories", "RESTRICT"),
        ("fk_quotes_customer_tenant", "quotes", ["organization_id", "customer_id"], "customers", "RESTRICT"),
        ("fk_quote_items_quote_tenant", "quote_items", ["organization_id", "quote_id"], "quotes", "CASCADE"),
        ("fk_projects_customer_tenant", "projects", ["organization_id", "customer_id"], "customers", "CASCADE"),
        ("fk_project_costs_project_tenant", "project_costs", ["organization_id", "project_id"], "projects", "CASCADE"),
    )
    for name, table, columns, referred_table, ondelete in constraints:
        op.create_foreign_key(
            name,
            table,
            referred_table,
            columns,
            ["organization_id", "id"],
            ondelete=ondelete,
        )


def downgrade() -> None:
    for name, table in (
        ("fk_project_costs_project_tenant", "project_costs"),
        ("fk_projects_customer_tenant", "projects"),
        ("fk_quote_items_quote_tenant", "quote_items"),
        ("fk_quotes_customer_tenant", "quotes"),
        ("fk_products_category_tenant", "products"),
    ):
        op.drop_constraint(name, table, type_="foreignkey")
    for table, constraint in reversed(PARENT_KEYS):
        op.drop_constraint(constraint, table, type_="unique")
