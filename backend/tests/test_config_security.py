import pytest
from pydantic import ValidationError

from app.core.config import Settings


def production_settings(**overrides):
    values = {
        "environment": "production",
        "secret_key": "a" * 48,
        "database_url": "postgresql+psycopg://user:pass@db.example.com:5432/marcenaria",
        "cors_origins": ["https://admin.example.com"],
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_accept_secure_values():
    settings = production_settings()
    assert settings.environment == "production"


@pytest.mark.parametrize(
    "overrides",
    [
        {"secret_key": "short"},
        {"secret_key": "change-me-in-production"},
        {"database_url": "postgresql+psycopg://postgres:postgres@localhost:5432/db"},
        {"cors_origins": ["http://localhost:3000"]},
        {"environment": "staging"},
        {"cors_origins": ["admin.example.com"]},
    ],
)
def test_production_settings_reject_insecure_values(overrides):
    with pytest.raises(ValidationError):
        production_settings(**overrides)
