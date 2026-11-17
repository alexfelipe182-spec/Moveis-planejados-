"""Runner staging checks also runnable with stdlib unittest, without services."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "delivery_validation_runner", ROOT / "scripts" / "validate_isolated.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ValidationStagingTests(unittest.TestCase):
    def test_recovery_sql_is_available_to_the_container_suite(self):
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary)
            relative = Path("database/multi_marcenarias_postgresql.sql")
            # The isolated suite intentionally has no .git directory or Git executable.
            with patch.object(runner, "run", return_value=relative.as_posix() + "\0"):
                runner.stage_sources(staging)
            self.assertTrue((staging / relative).is_file(), "Recovery test SQL missing from staging")
            self.assertEqual((staging / relative).read_bytes(), (ROOT / relative).read_bytes())

    def test_staging_excludes_env_variants_and_untracked_local_material(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            tracked = [
                "backend/app/main.py", "database/schema.sql", ".env.production.example",
                "backend/.env", "backend/.env.local", "database/.env.production",
            ]
            for relative in [*tracked, "backend/untracked-secret.txt"]:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative, encoding="utf-8")
            with patch.object(runner, "ROOT", source), patch.object(
                runner, "run", return_value="\0".join(tracked) + "\0"
            ) as git_files:
                runner.stage_sources(Path(target_dir))
            git_files.assert_called_once_with("git", "ls-files", "-z", "--cached", capture=True)
            copied = {path.relative_to(target_dir).as_posix()
                      for path in Path(target_dir).rglob("*") if path.is_file()}
            self.assertEqual(copied, {
                "backend/app/main.py", "database/schema.sql", ".env.production.example",
            })

if __name__ == "__main__":
    unittest.main()
