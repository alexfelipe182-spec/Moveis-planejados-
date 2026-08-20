import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_a_non_default_secret_key():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production", secret_key="change-me-in-production")


def test_production_accepts_a_configured_secret_key():
    settings = Settings(environment="production", secret_key="a-secure-production-secret")

    assert settings.secret_key == "a-secure-production-secret"
