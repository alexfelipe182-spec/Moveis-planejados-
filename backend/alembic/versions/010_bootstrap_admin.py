"""grant the selected bootstrap administrator

Revision ID: 010_bootstrap_admin
Revises: 009_materials_production_costs

The migration reads BOOTSTRAP_ADMIN_EMAIL only while the revision is applied.
It never stores the address in the repository or activity history.
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "010_bootstrap_admin"
down_revision = "009_materials_production_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    if not email:
        return

    connection = op.get_bind()
    user_id = connection.execute(
        sa.text(
            """
            SELECT id
            FROM users
            WHERE lower(email) = :email
              AND is_active IS TRUE
            """
        ),
        {"email": email},
    ).scalar_one_or_none()

    if user_id is None:
        raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL não corresponde a um usuário ativo")

    result = connection.execute(
        sa.text(
            """
            UPDATE users
            SET is_admin = TRUE
            WHERE id = :user_id
              AND is_admin IS FALSE
            """
        ),
        {"user_id": user_id},
    )

    if result.rowcount:
        connection.execute(
            sa.text(
                """
                INSERT INTO activities (
                    user_id,
                    action,
                    entity,
                    entity_id,
                    description,
                    created_at
                )
                VALUES (
                    :user_id,
                    'bootstrap_admin',
                    'user',
                    :user_id,
                    'Permissão administrativa inicial concedida',
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {"user_id": user_id},
        )


def downgrade() -> None:
    # A alteração de permissão é um evento de dados deliberado e auditado.
    # O rollback estrutural não deve remover privilégios automaticamente.
    pass
