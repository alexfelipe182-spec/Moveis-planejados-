import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import database_recovery as recovery

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "postgresql+psycopg://tester:secret-not-for-logs@127.0.0.1:5432/source_ci"
TARGET = "postgresql://tester:other-secret@localhost:5432/restore_ci"


@pytest.fixture
def pg_runner(monkeypatch):
    calls = []
    state = {"database": "restore_ci", "version": 180006, "sessions": 0, "objects": 0}

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if "--version" in command:
            stdout = f"{command[0]} (PostgreSQL) 18.6\n".encode()
        elif command[0] == "pg_dump":
            kwargs["stdout"].write(b"PGDMPsynthetic-backup-for-unit-tests")
            stdout = None
        elif command[0] == "psql":
            stdout = json.dumps(state).encode()
        else:
            stdout = b""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")

    monkeypatch.setattr(recovery.subprocess, "run", fake_run)
    monkeypatch.setenv("BACKUP_DATABASE_URL", SOURCE)
    monkeypatch.setenv("RESTORE_DATABASE_URL", TARGET)
    return calls, state


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sqlite:///secret",
        "postgresql://tester:secret@localhost",
        "postgresql://tester@localhost/db",
        "postgresql://tester:secret@localhost:99999/db",
        "postgresql://tester:secret@localhost:0/db",
        "postgresql://tester:secret@localhost/db?host=production",
        "postgresql://tester:secret@localhost/db?sslmode=disable&sslmode=require",
        "postgresql://tester:secret@remote.invalid/db?sslmode=disable",
        "postgresql://tester:secret@localhost/db#extra",
        "postgresql://tester:secret%00@localhost/db",
    ],
)
def test_rejects_ambiguous_urls_without_echoing_credentials(monkeypatch, value):
    monkeypatch.setenv("BACKUP_DATABASE_URL", value)
    with pytest.raises(recovery.RecoveryError) as error:
        recovery.connection_from_env("BACKUP_DATABASE_URL")
    assert "secret" not in str(error.value)


def test_credentials_are_decoded_and_only_in_child_environment(monkeypatch):
    monkeypatch.setenv(
        "BACKUP_DATABASE_URL",
        "postgresql://u%40ser:p%40ss%3Aword@remote.invalid/db?sslmode=require",
    )
    monkeypatch.setenv("PGHOSTADDR", "1.2.3.4")
    monkeypatch.setenv("PGSERVICE", "production")
    monkeypatch.setenv("PGOPTIONS", "-c unexpected=value")
    monkeypatch.setenv("RESEND_API_KEY", "not-for-postgres")
    connection = recovery.connection_from_env("BACKUP_DATABASE_URL")
    env = connection.environment(read_only=True)
    assert env["PGUSER"] == "u@ser"
    assert env["PGPASSWORD"] == "p@ss:word"
    assert env["PGSSLMODE"] == "require"
    assert "default_transaction_read_only=on" in env["PGOPTIONS"]
    assert "p@ss:word" not in repr(connection)
    assert not {"PGHOSTADDR", "PGSERVICE", "RESEND_API_KEY"} & env.keys()
    assert "unexpected" not in env["PGOPTIONS"]


def test_backup_creates_custom_archive_and_integrity_manifest(tmp_path, pg_runner):
    calls, _ = pg_runner
    archive = tmp_path / "test.dump"
    metadata = recovery.create_backup(archive)
    assert metadata == recovery.verify_backup(archive)
    assert metadata["size_bytes"] == archive.stat().st_size
    assert "source_fingerprint" in metadata
    assert "secret-not-for-logs" not in recovery.manifest_path(archive).read_text()
    dump_command, kwargs = next(
        call for call in calls if call[0][0] == "pg_dump" and "--version" not in call[0]
    )
    assert "--format=custom" in dump_command
    assert "secret-not-for-logs" not in str(dump_command)
    assert kwargs["env"]["PGPASSWORD"] == "secret-not-for-logs"
    assert "default_transaction_read_only=on" in kwargs["env"]["PGOPTIONS"]
    assert kwargs["stdin"] == subprocess.DEVNULL


@pytest.mark.parametrize("existing_name", ["test.dump", "test.dump.json"])
def test_backup_never_overwrites_existing_files(tmp_path, pg_runner, existing_name):
    calls, _ = pg_runner
    existing = tmp_path / existing_name
    existing.write_text("keep this file")
    with pytest.raises(recovery.RecoveryError, match="ja existe"):
        recovery.create_backup(tmp_path / "test.dump")
    assert existing.read_text() == "keep this file"
    assert not calls


def test_backup_refuses_old_pg_client(tmp_path, pg_runner, monkeypatch):
    monkeypatch.setattr(
        recovery.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=b"pg_dump (PostgreSQL) 16.2"
        ),
    )
    with pytest.raises(recovery.RecoveryError, match="versao principal 18"):
        recovery.create_backup(tmp_path / "test.dump")
    assert not (tmp_path / "test.dump").exists()


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.TimeoutExpired(["pg_dump"], 10, stderr=b"secret-not-for-logs"),
        OSError("secret-not-for-logs"),
        FileNotFoundError("secret-not-for-logs"),
    ],
)
def test_process_failures_are_redacted(monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(recovery.subprocess, "run", fail)
    with pytest.raises(recovery.RecoveryError) as error:
        recovery.run_pg(["pg_dump"], {})
    assert "secret-not-for-logs" not in str(error.value)


def test_failed_backup_is_not_restorable(tmp_path, pg_runner, monkeypatch):
    original = recovery.subprocess.run

    def fail_dump(command, **kwargs):
        if command[0] == "pg_dump" and "--version" not in command:
            kwargs["stdout"].write(b"PGDMPpartial")
            return SimpleNamespace(
                returncode=1, stdout=None, stderr=b"secret-not-for-logs"
            )
        return original(command, **kwargs)

    monkeypatch.setattr(recovery.subprocess, "run", fail_dump)
    archive = tmp_path / "failed.dump"
    with pytest.raises(recovery.RecoveryError) as error:
        recovery.create_backup(archive)
    assert "secret-not-for-logs" not in str(error.value)
    with pytest.raises(recovery.RecoveryError, match="incompleto"):
        recovery.verify_backup(archive)


def test_tampered_archive_is_rejected_before_restore(tmp_path, pg_runner):
    calls, _ = pg_runner
    archive = tmp_path / "test.dump"
    recovery.create_backup(archive)
    archive.write_bytes(archive.read_bytes() + b"tamper")
    calls.clear()
    with pytest.raises(recovery.RecoveryError, match="alterado"):
        recovery.restore_backup(archive, "restore_ci")
    assert not calls


def test_unexpected_manifest_data_is_never_echoed(tmp_path, pg_runner, capsys):
    archive = tmp_path / "test.dump"
    recovery.create_backup(archive)
    metadata_file = recovery.manifest_path(archive)
    metadata = json.loads(metadata_file.read_text())
    metadata["unexpected_secret"] = "never-log-this"
    metadata_file.write_text(json.dumps(metadata))
    assert recovery.main(["verify", "--archive", str(archive)]) == 1
    output = capsys.readouterr()
    assert "never-log-this" not in output.out + output.err


@pytest.mark.parametrize(
    "target,confirmation",
    [
        ("postgresql://u:secret@production.invalid/restore_ci", "restore_ci"),
        ("postgresql://u:secret@localhost/production", "production"),
        (TARGET, "restore_wrong"),
        (
            "postgresql://u:secret@127.0.0.1/restore_ci?hostaddr=production.invalid",
            "restore_ci",
        ),
    ],
)
def test_restore_rejects_nonisolated_or_unconfirmed_target(
    tmp_path, pg_runner, monkeypatch, target, confirmation
):
    calls, _ = pg_runner
    monkeypatch.setenv("RESTORE_DATABASE_URL", target)
    with pytest.raises(recovery.RecoveryError):
        recovery.restore_backup(tmp_path / "does-not-exist.dump", confirmation)
    assert not calls


def test_restore_rejects_original_database_even_with_loopback_alias(
    tmp_path, pg_runner, monkeypatch
):
    calls, _ = pg_runner
    monkeypatch.setenv(
        "BACKUP_DATABASE_URL", "postgresql://u:secret@127.0.0.1/restore_ci"
    )
    archive = tmp_path / "test.dump"
    recovery.create_backup(archive)
    calls.clear()
    with pytest.raises(recovery.RecoveryError, match="origem"):
        recovery.restore_backup(archive, "restore_ci")
    assert not calls


@pytest.mark.parametrize(
    "field,value",
    [("objects", 1), ("sessions", 1), ("database", "unexpected"), ("version", 160000)],
)
def test_restore_requires_empty_unused_matching_pg18_database(
    tmp_path, pg_runner, field, value
):
    calls, state = pg_runner
    archive = tmp_path / "test.dump"
    recovery.create_backup(archive)
    state[field] = value
    calls.clear()
    with pytest.raises(recovery.RecoveryError, match="vazio"):
        recovery.restore_backup(archive, "restore_ci")
    assert all(
        command[0] != "pg_restore" or "--version" in command for command, _ in calls
    )


def test_restore_is_single_transaction_and_never_clean_or_create(tmp_path, pg_runner):
    calls, _ = pg_runner
    archive = tmp_path / "test.dump"
    recovery.create_backup(archive)
    calls.clear()
    result = recovery.restore_backup(archive, "restore_ci")
    assert result["status"] == "restored_isolated"
    command, kwargs = calls[-1]
    assert "--single-transaction" in command
    assert "--exit-on-error" in command
    assert "--clean" not in command and "--create" not in command
    assert "--no-owner" in command and "--no-privileges" in command
    assert "other-secret" not in str(command)
    assert kwargs["env"]["PGDATABASE"] == "restore_ci"
    assert "default_transaction_read_only" not in kwargs["env"]["PGOPTIONS"]


def test_cli_reports_failure_without_secret_or_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BACKUP_DATABASE_URL", "secret-invalid-url")
    assert recovery.main(["backup", "--output", str(tmp_path / "test.dump")]) == 1
    output = capsys.readouterr()
    assert "ERRO:" in output.err
    assert "secret-invalid-url" not in output.err
    assert "Traceback" not in output.err
    assert not output.out


def test_production_compose_has_private_datastores_and_runtime_settings():
    compose = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text())
    services = compose["services"]
    assert services["postgres"]["image"].startswith("postgres:18-")
    assert services["postgres"]["volumes"] == ["postgres18_data:/var/lib/postgresql"]
    assert not services["postgres"].get("ports")
    assert not services["redis"].get("ports")
    assert services["app"]["ports"] == ["127.0.0.1:8000:8000"]
    assert set(services["app"]["depends_on"]) == {"postgres", "redis"}
    assert all(
        item["condition"] == "service_healthy"
        for item in services["app"]["depends_on"].values()
    )
    env = services["app"]["environment"]
    assert env["REDIS_URL"] == "redis://redis:6379/0"
    assert {
        "FRONTEND_URL",
        "DATABASE_CONNECT_TIMEOUT_SECONDS",
        "REDIS_TIMEOUT_SECONDS",
        "EMAIL_PROVIDER",
        "RESEND_API_KEY",
        "SMTP_TIMEOUT_SECONDS",
    } <= env.keys()


def test_recovery_workflow_uses_only_disposable_databases():
    path = ROOT / ".github" / "workflows" / "recovery.yml"
    workflow = yaml.safe_load(path.read_text())
    job = workflow["jobs"]["recovery-drill"]
    assert job["services"]["postgres"]["image"].startswith("postgres:18-")
    assert job["env"]["BACKUP_DATABASE_URL"].endswith(
        "@127.0.0.1:5432/recovery_source_ci"
    )
    assert job["env"]["RESTORE_DATABASE_URL"].endswith("@127.0.0.1:5432/restore_ci")
    assert "secrets." not in path.read_text()
    assert not any("upload-artifact" in step.get("uses", "") for step in job["steps"])
