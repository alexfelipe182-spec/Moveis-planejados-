"""Export the complete PostgreSQL migration chain without connecting to a database."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMPTY_SCHEMA_GUARD = """-- Multi-Marcenarias: PostgreSQL, banco/schema NOVO e vazio somente.
-- Gerado pelas migracoes Alembic; nao recupera registros de um banco perdido.
-- Para banco existente: backup primeiro, depois alembic upgrade head.
BEGIN;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
    ) THEN
        RAISE EXCEPTION 'Schema nao vazio: use backup e alembic upgrade head';
    END IF;
END $$;
"""


def export_sql() -> str:
    # Offline mode never connects. Explicit non-production settings keep the
    # export independent of production credentials and optional admin bootstrap.
    env = os.environ.copy()
    env.update({
        "ENVIRONMENT": "development",
        "DATABASE_URL": "postgresql+psycopg://localhost/marcenaria_schema_export",
        "BOOTSTRAP_ADMIN_EMAIL": "",
    })
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT / "backend", env=env, check=True, capture_output=True, text=True,
        encoding="utf-8",
    )
    sql = result.stdout
    if not sql.startswith("BEGIN;") or not sql.rstrip().endswith("COMMIT;"):
        raise RuntimeError("Exportacao Alembic incompleta; nenhum arquivo foi gravado")
    return EMPTY_SCHEMA_GUARD + sql[len("BEGIN;"):]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "database" / "multi_marcenarias_postgresql.sql")
    args = parser.parse_args()
    try:
        sql = export_sql()
    except subprocess.CalledProcessError as exc:
        # No SQL is written on failure. Keep an earlier valid artifact intact.
        raise SystemExit(f"Falha ao exportar migracoes:\n{exc.stderr}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(sql, encoding="utf-8")
    temporary.replace(args.output)
    print(f"SQL PostgreSQL gerado: {args.output}")


if __name__ == "__main__":
    main()
