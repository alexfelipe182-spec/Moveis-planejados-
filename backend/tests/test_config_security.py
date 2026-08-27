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


def test_smtp_security_modes_are_mutually_exclusive():
    with pytest.raises(ValidationError):
        production_settings(smtp_starttls=True, smtp_use_ssl=True)


def test_partial_smtp_configuration_is_rejected():
    with pytest.raises(ValidationError):
        production_settings(smtp_host="smtp.example.com")


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


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_connect_timeout_seconds": 0},
        {"database_connect_timeout_seconds": 1},
        {"database_connect_timeout_seconds": -1},
        {"redis_timeout_seconds": 0},
        {"redis_timeout_seconds": -1},
        {"redis_timeout_seconds": float("inf")},
        {"redis_timeout_seconds": float("nan")},
    ],
)
def test_dependency_timeouts_reject_unbounded_or_invalid_values(overrides):
    with pytest.raises(ValidationError):
        production_settings(**overrides)


def test_dependency_timeouts_accept_custom_positive_values():
    settings = production_settings(database_connect_timeout_seconds=8, redis_timeout_seconds=0.5)
    assert settings.database_connect_timeout_seconds == 8
    assert settings.redis_timeout_seconds == 0.5
