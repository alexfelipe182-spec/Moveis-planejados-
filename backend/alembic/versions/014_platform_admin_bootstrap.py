"""grant an explicitly selected platform administrator"""

import os

import sqlalchemy as sa
from alembic import op

revision = "014_platform_admin_bootstrap"
down_revision = "013_plans_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    email = os.getenv("BOOTSTRAP_PLATFORM_ADMIN_EMAIL", "").strip().lower()
    if not email:
        return
    connection = op.get_bind()
    result = connection.execute(
        sa.text("UPDATE users SET is_platform_admin = TRUE WHERE lower(email) = :email AND is_active IS TRUE"),
        {"email": email},
    )
    if result.rowcount != 1:
        raise RuntimeError("BOOTSTRAP_PLATFORM_ADMIN_EMAIL não corresponde a exatamente um usuário ativo")


def downgrade() -> None:
    pass

