import os

from app.core.config import settings
from app.services.openai_config import openai_api_key, openai_model


STRIPE_PRICE_ENV = {
    "starter": "STRIPE_PRICE_STARTER",
    "professional": "STRIPE_PRICE_PROFESSIONAL",
    "business": "STRIPE_PRICE_BUSINESS",
}


def _configured(value: str | None) -> bool:
    return bool(value and value.strip())


def get_integration_status() -> dict[str, object]:
    """Retorna apenas estado de configuração; nunca retorna credenciais ou tokens."""
    smtp_ready = all(
        _configured(value)
        for value in (
            settings.smtp_host,
            settings.smtp_user,
            settings.smtp_password,
            settings.smtp_from,
        )
    )

    stripe_secret_ready = _configured(os.getenv("STRIPE_SECRET_KEY"))
    stripe_webhook_ready = _configured(os.getenv("STRIPE_WEBHOOK_SECRET"))
    stripe_prices = {
        plan: _configured(os.getenv(env_name))
        for plan, env_name in STRIPE_PRICE_ENV.items()
    }

    return {
        "environment": settings.environment,
        "openai": {
            "configured": bool(openai_api_key()),
            "model": openai_model(),
        },
        "email": {
            "configured": smtp_ready,
            "transport": "ssl" if settings.smtp_use_ssl else "starttls" if settings.smtp_starttls else "plain",
        },
        "stripe": {
            "secret_configured": stripe_secret_ready,
            "webhook_configured": stripe_webhook_ready,
            "prices_configured": stripe_prices,
            "checkout_ready": stripe_secret_ready and any(stripe_prices.values()),
            "fully_configured": (
                stripe_secret_ready
                and stripe_webhook_ready
                and all(stripe_prices.values())
            ),
        },
    }
