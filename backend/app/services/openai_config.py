import os

from app.core.config import settings


def openai_api_key() -> str | None:
    if os.getenv("OPENAI_API_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return None
    if "OPENAI_API_KEY" in os.environ:
        return os.getenv("OPENAI_API_KEY") or None
    if settings.openai_api_key is None:
        return None
    return settings.openai_api_key.get_secret_value()


def openai_model() -> str:
    return os.getenv("OPENAI_MODEL") or settings.openai_model
