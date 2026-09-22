"""Container-only validation entrypoint; refuses inherited or unexpected targets."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    from app.core.config import settings

    expected_db = "postgresql+psycopg://postgres:isolated-test-only@postgres:5432/mm_validation"
    expected_redis = "redis://redis:6379/0"
    if (settings.environment != "test" or settings.database_url != expected_db
            or settings.redis_url != expected_redis or Path(".env").exists()):
        raise RuntimeError("Refusing migrations: destinations are not isolated validation services")
    print("Confirmed: PostgreSQL postgres:5432/mm_validation; Redis redis:6379/0; environment=test", flush=True)
    if any(os.getenv(key) for key in ("SMTP_HOST", "STRIPE_SECRET_KEY", "OPENAI_API_KEY", "BOOTSTRAP_ADMIN_EMAIL")):
        raise RuntimeError("External credentials must not be supplied")
    import redis
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    heads = tuple(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
    assert len(heads) == 1, heads
    assert redis.Redis.from_url(expected_redis).ping()
    for command in (
        ["ruff", "check", ".", "../scripts", "../frontend_server.py"],
        [sys.executable, "-m", "compileall", "-q", ".", "../scripts", "../frontend_server.py"],
        [sys.executable, "-m", "pip", "check"],
        ["alembic", "upgrade", "head"], ["alembic", "check"], ["alembic", "current"],
    ):
        subprocess.run(command, check=True)
    engine = create_engine(expected_db)
    with engine.connect() as connection:
        assert tuple(MigrationContext.configure(connection).get_current_heads()) == heads
    engine.dispose()
    subprocess.run([sys.executable, "-m", "pytest", "-q", "tests", "--maxfail=1", "--strict-config",
                    "--cov=app", "--cov-fail-under=80", "--cov-report=term-missing"], check=True)


if __name__ == "__main__":
    main()
