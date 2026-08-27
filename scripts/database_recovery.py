"""Logical PG18 backup and deliberately restricted, isolated restore drill.

No credentials are put in process arguments or diagnostic output. This tool
does not schedule backups, encrypt archives, or restore over production data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from urllib.parse import parse_qs, unquote, urlsplit

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
PG_MAJOR = 18
PROCESS_TIMEOUT = 900
MANIFEST_KEYS = {
    "format_version",
    "created_at",
    "pg_major",
    "source_fingerprint",
    "size_bytes",
    "sha256",
}
EMPTY_TARGET_QUERY = """
SELECT json_build_object(
    'database', current_database(),
    'version', current_setting('server_version_num')::int,
    'sessions', (SELECT count(*) FROM pg_stat_activity
                 WHERE datname = current_database() AND pid <> pg_backend_pid()),
    'objects',
      (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') +
      (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') +
      (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') +
      (SELECT count(*) FROM pg_namespace
        WHERE nspname !~ '^pg_' AND nspname NOT IN ('public', 'information_schema')) +
      (SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql') +
      (SELECT count(*) FROM pg_largeobject_metadata)
)
"""


class RecoveryError(Exception):
    """Safe, credential-free error suitable for a command-line diagnostic."""


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)
    sslmode: str = "require"

    @property
    def fingerprint(self) -> str:
        host = "loopback" if self.host in LOOPBACK_HOSTS else self.host
        return hashlib.sha256(
            f"{host}:{self.port}/{self.database}".encode()
        ).hexdigest()

    def environment(self, *, read_only: bool) -> dict[str, str]:
        # Do not inherit PGHOSTADDR, PGSERVICE, PGOPTIONS, a .psqlrc, or unrelated
        # provider credentials from the caller. All connection settings are explicit.
        allowed = {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "LD_LIBRARY_PATH",
        }
        env = {
            key: value for key, value in os.environ.items() if key.upper() in allowed
        }
        env.update(
            PGHOST=self.host,
            PGPORT=str(self.port),
            PGDATABASE=self.database,
            PGUSER=self.username,
            PGPASSWORD=self.password,
            PGSSLMODE=self.sslmode,
            PGCONNECT_TIMEOUT="10",
            PGAPPNAME="moveis-recovery",
            PGOPTIONS="-c lock_timeout=10000 -c statement_timeout=840000"
            + (" -c default_transaction_read_only=on" if read_only else ""),
        )
        return env


def connection_from_env(name: str) -> Connection:
    try:
        raw = os.environ.get(name, "")
        url = urlsplit(raw)
        if (
            url.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}
            or url.fragment
        ):
            raise ValueError
        host = (url.hostname or "").lower().rstrip(".")
        database = unquote(url.path.removeprefix("/"))
        username = unquote(url.username or "")
        password = unquote(url.password or "")
        port = url.port if url.port is not None else 5432
        values = (host, database, username, password)
        if not all(values) or any(
            any(ord(char) < 32 for char in value) for value in values
        ):
            raise ValueError
        if (
            any(char.isspace() for char in host)
            or "/" in database
            or not 1 <= port <= 65535
        ):
            raise ValueError
        options = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
        if set(options) - {"sslmode"} or any(
            len(value) != 1 for value in options.values()
        ):
            raise ValueError
        sslmode = options.get(
            "sslmode", ["disable" if host in LOOPBACK_HOSTS else "require"]
        )[0]
        if sslmode not in {"disable", "require", "verify-ca", "verify-full"}:
            raise ValueError
        if host not in LOOPBACK_HOSTS and sslmode == "disable":
            raise ValueError
        return Connection(host, port, database, username, password, sslmode)
    except (ValueError, TypeError):
        raise RecoveryError(
            f"{name}: use uma URL PostgreSQL com host, banco, usuario e senha; "
            "a unica opcao de URL aceita e sslmode (TLS obrigatorio fora de loopback)."
        ) from None


def run_pg(
    command: list[str],
    env: dict[str, str],
    *,
    stdout: BinaryIO | None = None,
    timeout: int = PROCESS_TIMEOUT,
) -> bytes:
    try:
        result = subprocess.run(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout if stdout is not None else subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise RecoveryError(
            f"Instale o cliente PostgreSQL {PG_MAJOR} e inclua {command[0]} no PATH."
        ) from None
    except (subprocess.TimeoutExpired, OSError):
        raise RecoveryError(
            f"{command[0]} nao concluiu. Confira o prazo, a conexao e as permissoes locais."
        ) from None
    if result.returncode:
        # PostgreSQL stderr can include credentials from a malformed connection or
        # sensitive SQL/data. Never echo it or a subprocess exception to CI/logs.
        raise RecoveryError(
            f"{command[0]} falhou (codigo {result.returncode}); nenhum sucesso foi confirmado."
        )
    return result.stdout or b""


def require_pg18(binary: str, env: dict[str, str]) -> None:
    version = run_pg([binary, "--version"], env, timeout=10).decode(
        "utf-8", errors="replace"
    )
    match = re.search(r"\(PostgreSQL\)\s+(\d+)\.", version)
    if match is None or int(match.group(1)) != PG_MAJOR:
        raise RecoveryError(
            f"Use {binary} da versao principal {PG_MAJOR} para este procedimento."
        )


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def manifest_path(archive: Path) -> Path:
    return archive.with_name(archive.name + ".json")


def create_backup(archive: Path) -> dict:
    source = connection_from_env("BACKUP_DATABASE_URL")
    env = source.environment(read_only=True)
    archive = archive.absolute()
    metadata_file = manifest_path(archive)
    if (
        archive.exists()
        or metadata_file.exists()
        or archive.is_symlink()
        or metadata_file.is_symlink()
    ):
        raise RecoveryError(
            "O arquivo de backup ou manifesto ja existe; escolha um nome novo."
        )
    if archive.suffix != ".dump" or not archive.parent.is_dir():
        raise RecoveryError(
            "Use um arquivo .dump em um diretorio existente, privado e fora do repositorio."
        )
    require_pg18("pg_dump", env)
    require_pg18("pg_restore", env)
    # O_EXCL prevents overwriting even if the destination appears after the check.
    # Reserve both paths before contacting the source. On failure keep the partial
    # archive/empty manifest; verify/restore reject it, and no old file is removed.
    try:
        with metadata_file.open("x", encoding="utf-8") as metadata_stream:
            with archive.open("xb") as output:
                if os.name != "nt":
                    os.fchmod(output.fileno(), 0o600)
                    os.fchmod(metadata_stream.fileno(), 0o600)
                run_pg(
                    [
                        "pg_dump",
                        "--no-password",
                        "--format=custom",
                        "--no-privileges",
                        "--lock-wait-timeout=10000",
                    ],
                    env,
                    stdout=output,
                )
                output.flush()
                os.fsync(output.fileno())
            with archive.open("rb") as header:
                if header.read(5) != b"PGDMP":
                    raise RecoveryError(
                        "O backup nao possui o formato custom esperado."
                    )
            run_pg(["pg_restore", "--list", str(archive)], env, timeout=30)
            metadata = {
                "format_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pg_major": PG_MAJOR,
                "source_fingerprint": source.fingerprint,
                "size_bytes": archive.stat().st_size,
                "sha256": digest_file(archive),
            }
            json.dump(metadata, metadata_stream, indent=2)
            metadata_stream.write("\n")
            metadata_stream.flush()
            os.fsync(metadata_stream.fileno())
    except FileExistsError:
        raise RecoveryError(
            "O destino apareceu durante a operacao; nenhum arquivo existente foi sobrescrito."
        ) from None
    except OSError:
        raise RecoveryError(
            "Nao foi possivel gravar o backup. Considere incompletos os arquivos desta tentativa."
        ) from None
    return metadata


def verify_backup(archive: Path) -> dict:
    try:
        metadata_file = manifest_path(archive)
        if (
            not archive.is_file()
            or archive.is_symlink()
            or not metadata_file.is_file()
            or metadata_file.is_symlink()
            or metadata_file.stat().st_size > 4096
        ):
            raise ValueError
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if (
            not isinstance(metadata, dict)
            or set(metadata) != MANIFEST_KEYS
            or metadata.get("format_version") != 1
            or metadata.get("pg_major") != PG_MAJOR
        ):
            raise ValueError
        if datetime.fromisoformat(metadata["created_at"]).tzinfo is None:
            raise ValueError
        if not re.fullmatch(
            r"[a-f0-9]{64}", str(metadata.get("source_fingerprint", ""))
        ):
            raise ValueError
        if metadata.get("size_bytes") != archive.stat().st_size or metadata.get(
            "sha256"
        ) != digest_file(archive):
            raise ValueError
        with archive.open("rb") as header:
            if header.read(5) != b"PGDMP":
                raise ValueError
        return metadata
    except (OSError, ValueError, TypeError):
        raise RecoveryError(
            "Backup/manifesto ausente, incompleto ou alterado; a restauracao foi recusada."
        ) from None


def restore_backup(archive: Path, confirm_target: str) -> dict:
    target = connection_from_env("RESTORE_DATABASE_URL")
    if target.host not in LOOPBACK_HOSTS:
        raise RecoveryError(
            "Restauracao permitida somente em PostgreSQL local/descartavel (host loopback)."
        )
    if (
        not re.fullmatch(r"restore_[a-z0-9_]+", target.database)
        or confirm_target != target.database
    ):
        raise RecoveryError(
            "O banco deve comecar com restore_ e coincidir exatamente com --confirm-target."
        )
    metadata = verify_backup(archive)
    if target.fingerprint == metadata["source_fingerprint"]:
        raise RecoveryError(
            "O destino coincide com a origem; restauracao no banco original foi recusada."
        )
    env = target.environment(read_only=False)
    require_pg18("psql", env)
    require_pg18("pg_restore", env)
    raw_state = run_pg(
        [
            "psql",
            "--no-psqlrc",
            "--no-password",
            "--set=ON_ERROR_STOP=1",
            "--tuples-only",
            "--no-align",
            "--command",
            EMPTY_TARGET_QUERY,
        ],
        target.environment(read_only=True),
        timeout=30,
    )
    try:
        state = json.loads(raw_state)
        if (
            state["database"] != target.database
            or state["version"] // 10000 != PG_MAJOR
            or state["objects"] != 0
            or state["sessions"] != 0
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise RecoveryError(
            "O destino precisa ser PG18, vazio e sem outras sessoes. Nada foi restaurado."
        ) from None
    run_pg(
        [
            "pg_restore",
            "--no-password",
            "--no-owner",
            "--no-privileges",
            "--no-tablespaces",
            "--single-transaction",
            "--exit-on-error",
            "--dbname",
            target.database,
            str(archive.absolute()),
        ],
        env,
    )
    return {
        "status": "restored_isolated",
        "database": target.database,
        "sha256": metadata["sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backup PG18 e ensaio de restauracao isolada; consulte docs/operations.md."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser(
        "backup", help="Exportar BACKUP_DATABASE_URL sem alterar a origem"
    )
    backup.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser(
        "verify",
        help="Conferir integridade do arquivo e manifesto (nao prova recuperacao)",
    )
    verify.add_argument("--archive", type=Path, required=True)
    restore = commands.add_parser(
        "restore", help="Restaurar RESTORE_DATABASE_URL local, isolado e vazio"
    )
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--confirm-target", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            result = {"status": "backup_created", **create_backup(args.output)}
        elif args.command == "verify":
            result = {"status": "integrity_verified", **verify_backup(args.archive)}
        else:
            result = restore_backup(args.archive, args.confirm_target)
    except RecoveryError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
