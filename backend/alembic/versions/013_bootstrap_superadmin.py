"""promote the legacy platform owner to superadmin

Revision ID: 013_bootstrap_superadmin
Revises: 012_quote_intelligence

The email remains an environment concern and is never stored in source control.
BOOTSTRAP_SUPERADMIN_EMAIL takes precedence; BOOTSTRAP_ADMIN_EMAIL is accepted
as a safe migration path for the legacy single-tenant installation.
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "013_bootstrap_superadmin"
down_revision = "012_quote_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    email = (
        os.getenv("BOOTSTRAP_SUPERADMIN_EMAIL", "").strip().lower()
        or os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    )
    if not email:
        return

    connection = op.get_bind()
    row = connection.execute(
        sa.text(
            """
            SELECT id, tenant_id
            FROM users
            WHERE lower(email) = :email
              AND is_active IS TRUE
              AND is_admin IS TRUE
            """
        ),
        {"email": email},
    ).one_or_none()
    if row is None:
        raise RuntimeError("E-mail de bootstrap não corresponde a um administrador ativo")

    result = connection.execute(
        sa.text(
            """
            UPDATE users
            SET is_superadmin = TRUE
            WHERE id = :user_id
              AND is_superadmin IS FALSE
            """
        ),
        {"user_id": row.id},
    )
    if result.rowcount:
        connection.execute(
            sa.text(
                """
                INSERT INTO activities (
                    tenant_id,
                    user_id,
                    action,
                    entity,
                    entity_id,
                    description,
                    created_at
                )
                VALUES (
                    :tenant_id,
                    :user_id,
                    'bootstrap_superadmin',
                    'user',
                    :user_id,
                    'Permissão de superadministrador da plataforma concedida',
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {"tenant_id": row.tenant_id, "user_id": row.id},
        )


def downgrade() -> None:
    # Privilégios são eventos de segurança deliberados; rollback estrutural
    # não remove acesso administrativo automaticamente.
    pass
