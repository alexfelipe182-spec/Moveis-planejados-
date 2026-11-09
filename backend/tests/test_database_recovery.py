"""Exercise real PostgreSQL migrations, including populated legacy upgrades."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.database import Base, engine


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def migration_database():
    # conftest validates the disposable database before importing this module.
    schema = "recovery_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    target = create_engine(url)
    try:
        yield target
    finally:
        target.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def alembic(target, revision, *, offline=False, bootstrap=""):
    env = dict(os.environ, DATABASE_URL=target.url.render_as_string(hide_password=False),
               BOOTSTRAP_ADMIN_EMAIL=bootstrap)
    args = [sys.executable, "-m", "alembic", "upgrade", revision]
    if offline:
        args.append("--sql")
    return subprocess.run(args, cwd=ROOT / "backend", env=env, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def apply_sql(target, sql):
    with target.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)


def assert_schema_matches_models(target):
    with target.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "017_customer_portal"
        assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_exported_sql_builds_complete_schema_and_refuses_reapplication(migration_database, tmp_path):
    destination = tmp_path / "recovery.sql"
    subprocess.run([sys.executable, str(ROOT / "scripts/export_database_sql.py"),
                    "--output", str(destination)], check=True, capture_output=True)
    sql = destination.read_text(encoding="utf-8")
    assert sql == (ROOT / "database/multi_marcenarias_postgresql.sql").read_text(encoding="utf-8")
    apply_sql(migration_database, sql)
    assert_schema_matches_models(migration_database)
    with migration_database.connect() as connection:
        days = connection.scalar(text("SELECT EXTRACT(EPOCH FROM (trial_end-created_at))/86400 FROM subscriptions"))
        assert days == 30
    with pytest.raises(DBAPIError, match="Schema nao vazio"):
        apply_sql(migration_database, sql)
    assert_schema_matches_models(migration_database)


@pytest.mark.parametrize("offline", [False, True])
def test_populated_legacy_upgrade_preserves_records_and_links(migration_database, offline):
    alembic(migration_database, "010_bootstrap_admin")
    with migration_database.begin() as connection:
        connection.execute(text("INSERT INTO users (name,email,password_hash,created_at) VALUES ('Legacy','legacy@example.com','unused',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO customers (name,created_at) VALUES ('Cliente antigo',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO categories (name) VALUES ('Cozinha')"))
        connection.execute(text("INSERT INTO products (category_id,name,price) SELECT id,'Armario',1200 FROM categories"))
        connection.execute(text("INSERT INTO quotes (customer_id,description,total,status,created_at,updated_at) SELECT id,'Orcamento antigo',1200,'pending',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM customers"))
    if offline:
        apply_sql(migration_database, alembic(migration_database, "010_bootstrap_admin:head", offline=True))
    else:
        alembic(migration_database, "head")
    assert_schema_matches_models(migration_database)
    with migration_database.connect() as connection:
        tenant = connection.scalar(text("SELECT id FROM tenants WHERE slug='legacy-default'"))
        for table in ("users", "customers", "categories", "products", "quotes"):
            assert connection.scalar(text(f"SELECT count(*) FROM {table} WHERE tenant_id=:tenant"), {"tenant": tenant}) == 1
        assert connection.scalar(text("SELECT p.price FROM products p JOIN categories c ON c.id=p.category_id")) == 1200
        assert connection.scalar(text("SELECT q.total FROM quotes q JOIN customers c ON c.id=q.customer_id")) == 1200
        assert connection.scalar(text("SELECT trial_end IS NOT NULL FROM subscriptions")) is True
    # Running the normal deploy command again must preserve the same data.
    alembic(migration_database, "head")


def test_trial_migration_preserves_existing_paid_and_dated_trials(migration_database):
    alembic(migration_database, "014_guided_onboarding")
    with migration_database.begin() as connection:
        for slug, status, trial_end in (("paid", "active", None), ("dated", "trialing", "2020-01-01"), ("missing", "trialing", None)):
            tenant = connection.scalar(text("INSERT INTO tenants (name,slug) VALUES (:slug,:slug) RETURNING id"), {"slug": slug})
            connection.execute(text("INSERT INTO subscriptions (tenant_id,status,trial_end,created_at,updated_at) VALUES (:tenant,:status,:trial_end,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),
                               {"tenant": tenant, "status": status, "trial_end": trial_end})
    apply_sql(migration_database, alembic(migration_database, "014_guided_onboarding:015_trial_30_days", offline=True))
    with migration_database.connect() as connection:
        rows = {row.slug: row for row in connection.execute(text("SELECT t.slug,s.status,s.trial_end FROM subscriptions s JOIN tenants t ON t.id=s.tenant_id"))}
        assert rows["paid"].status == "active" and rows["paid"].trial_end is None
        assert str(rows["dated"].trial_end) == "2020-01-01 00:00:00"
        assert rows["missing"].trial_end is not None


def test_offline_admin_bootstrap_fails_explicitly(migration_database):
    with pytest.raises(subprocess.CalledProcessError) as failure:
        alembic(migration_database, "009_materials_production_costs:010_bootstrap_admin",
                offline=True, bootstrap="admin@example.com")
    assert "exige migração online" in failure.value.stderr
