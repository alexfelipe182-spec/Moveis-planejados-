"""Run delivery gates with disposable PostgreSQL/Redis and no test egress."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, capture=False, cwd=ROOT):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def cleanup(*args):
    """Attempt one cleanup operation without preventing the remaining ones."""
    result = subprocess.run(args, cwd=ROOT, check=False, text=True, capture_output=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no details"
        print(f"Cleanup warning ({' '.join(args)}): {detail}", file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="Existing Python 3.12 image with requirements and pytest-cov")
    args = parser.parse_args()
    name = "mm-validation-" + uuid.uuid4().hex[:12]
    created = []
    network_created = False
    image_created = False
    image = args.image or name
    print(f"Execution: {name}", flush=True)
    with tempfile.TemporaryDirectory(prefix=name + "-") as temporary:
        staging = Path(temporary)
        # Copy only files already tracked by Git; untracked local material may contain secrets.
        files = run("git", "ls-files", "-z", "--cached", capture=True)
        for relative in files.split("\0"):
            path = Path(relative)
            if not relative or (relative != ".env.production.example" and any(part.startswith(".env") for part in path.parts)):
                continue
            if path.parts[0] not in {"backend", "frontend", "scripts", "tests", ".github", "docs"} and relative not in {"frontend_server.py", "requirements-frontend.txt", "render.yaml", ".env.production.example"}:
                continue
            source = ROOT / path
            if source.is_file():
                target = staging / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        try:
            if not args.image:
                build_context = staging / ".validation-image"
                build_context.mkdir()
                shutil.copyfile(staging / "backend" / "requirements.txt", build_context / "requirements.txt")
                (build_context / "Dockerfile").write_text(
                    "FROM python:3.12-slim\n"
                    "COPY requirements.txt /tmp/requirements.txt\n"
                    "RUN pip install --no-cache-dir -r /tmp/requirements.txt pytest-cov pip-audit\n",
                    encoding="utf-8",
                )
                run("docker", "build", "-t", image, str(build_context))
                image_created = True
            run("docker", "network", "create", "--internal", name)
            network_created = True
            for service, service_image, options in (
                ("postgres", "postgres:16-bookworm", ["--tmpfs", "/var/lib/postgresql/data", "-e", "POSTGRES_DB=mm_validation", "-e", "POSTGRES_PASSWORD=isolated-test-only"]),
                ("redis", "redis:7", []),
            ):
                container = run("docker", "run", "-d", "--network", name, "--network-alias", service,
                                "--label", f"mm.validation={name}", *options, service_image, capture=True).strip()
                created.append(container)
            for container, command in ((created[0], ["pg_isready", "-U", "postgres", "-d", "mm_validation"]),
                                       (created[1], ["redis-cli", "ping"])):
                for _attempt in range(60):
                    probe = subprocess.run(
                        ["docker", "exec", container, *command], check=False, capture_output=True
                    )
                    if probe.returncode == 0:
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("Temporary service did not become ready")
            internal = json.loads(run("docker", "network", "inspect", name, capture=True))[0]["Internal"]
            assert internal, "Test network must block external traffic"
            run("docker", "run", "--rm", "--network", name,
                "--mount", f"type=bind,src={staging},dst=/workspace",
                "--workdir", "/workspace/backend", "--entrypoint", "env", image,
                "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp", "PYTHONPATH=/workspace/backend",
                "ENVIRONMENT=test", "DATABASE_URL=postgresql+psycopg://postgres:isolated-test-only@postgres:5432/mm_validation",
                "REDIS_URL=redis://redis:6379/0", "SECRET_KEY=isolated-validation-secret-at-least-32-bytes",
                "OPENAI_ENABLED=true", "OPENAI_API_DISABLED=true", "OPENAI_API_KEY=",
                "RATE_LIMIT_PER_MINUTE=120", "python", "/workspace/scripts/validation_gates.py")
            run("docker", "run", "--rm", "--network", "none",
                "--mount", f"type=bind,src={staging},dst=/workspace,readonly",
                "--workdir", "/workspace/frontend", "node:22-alpine", "sh", "-ec",
                "for file in *.js *.cjs; do node --check \"$file\"; done; node --test *.test.cjs")
            # Only the dependency manifest goes to the online audit container.
            run("docker", "run", "--rm", "--entrypoint", "env",
                "--mount", f"type=bind,src={staging / 'backend' / 'requirements.txt'},dst=/requirements.txt,readonly",
                image, "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp",
                "python", "-m", "pip_audit", "-r", "/requirements.txt")
        finally:
            # IDs come only from successful creates in this invocation. No global prune/down.
            for container in reversed(created):
                cleanup("docker", "rm", "-f", "-v", container)
            if network_created:
                cleanup("docker", "network", "rm", name)
            if image_created:
                cleanup("docker", "image", "rm", image)


if __name__ == "__main__":
    main()
