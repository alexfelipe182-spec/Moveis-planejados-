"""Synthetic recovery exercise; deliberately limited to disposable local CI DBs."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from database_recovery import LOOPBACK_HOSTS, RecoveryError, connection_from_env
from sqlalchemy import URL, create_engine, inspect, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]


def isolated_engine(env_name: str, expected_database: str):
    connection = connection_from_env(env_name)
    if (
        connection.host not in LOOPBACK_HOSTS
        or connection.database != expected_database
    ):
        raise RecoveryError(
            "O ensaio aceita somente os bancos locais descartaveis definidos no CI."
        )
    url = URL.create(
        "postgresql+psycopg",
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        password=connection.password,
        query={"sslmode": connection.sslmode},
    )
    return create_engine(url, connect_args={"connect_timeout": 5})


def seed() -> None:
    from app.models import Customer, Project, Quote, QuoteItem

    engine = isolated_engine("BACKUP_DATABASE_URL", "recovery_source_ci")
    try:
        with Session(engine) as session:
            if session.scalar(select(Customer.id).limit(1)) is not None:
                raise RecoveryError(
                    "Origem do ensaio ja contem clientes; semear foi recusado."
                )
            customer = Customer(
                name="Cliente Sintético - Recuperação", email="recovery@example.invalid"
            )
            session.add(customer)
            session.flush()
            quote = Quote(
                customer_id=customer.id,
                description="Orçamento sintético de recuperação",
                status="approved",
                total=Decimal("1234.56"),
                suggested_total=Decimal("1234.56"),
            )
            session.add(quote)
            session.flush()
            session.add(
                QuoteItem(
                    quote_id=quote.id,
                    name="Armário teste",
                    quantity=Decimal(2),
                    unit_price=Decimal("617.28"),
                    subtotal=Decimal("1234.56"),
                )
            )
            session.add(
                Project(
                    customer_id=customer.id,
                    name="Projeto sintético",
                    photos=["https://example.invalid/recovery.png"],
                )
            )
            session.commit()
    finally:
        engine.dispose()
    print("Dados sinteticos criados somente em recovery_source_ci.")


def snapshot(engine) -> dict:
    result = {}
    with engine.connect() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))
        for name in sorted(inspect(connection).get_table_names(schema="public")):
            quoted = engine.dialect.identifier_preparer.quote(name)
            query = text(
                f"SELECT to_jsonb(record) FROM public.{quoted} AS record ORDER BY to_jsonb(record)::text"
            )
            result[name] = connection.execute(query).scalars().all()
    return result


def verify() -> None:
    source = isolated_engine("BACKUP_DATABASE_URL", "recovery_source_ci")
    target = isolated_engine("RESTORE_DATABASE_URL", "restore_ci")
    try:
        original = snapshot(source)
        restored = snapshot(target)
        if original != restored:
            raise RecoveryError("O conteudo restaurado difere da origem sintetica.")
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
        expected = ScriptDirectory.from_config(config).get_current_head()
        if restored.get("alembic_version") != [{"version_num": expected}]:
            raise RecoveryError(
                "A revisao Alembic restaurada nao corresponde ao codigo."
            )
        if not all(
            restored.get(name)
            for name in ("customers", "quotes", "quote_items", "projects")
        ):
            raise RecoveryError(
                "O ensaio nao possui os registros sinteticos esperados."
            )
        print(
            json.dumps(
                {
                    "status": "recovery_drill_passed",
                    "tables": len(restored),
                    "alembic_revision": expected,
                }
            )
        )
    finally:
        source.dispose()
        target.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seed", "verify"))
    command = parser.parse_args().command
    if command == "seed":
        seed()
    else:
        verify()
