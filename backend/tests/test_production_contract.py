import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def test_production_env_example_matches_runtime_contract():
    values = _read_env(ROOT / ".env.production.example")
    required = {
        "ENVIRONMENT",
        "DATABASE_URL",
        "REDIS_URL",
        "RATE_LIMIT_PER_MINUTE",
        "SECRET_KEY",
        "JWT_ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "CORS_ORIGINS",
        "FRONTEND_URL",
        "PASSWORD_RESET_EXPIRE_MINUTES",
        "SMTP_STARTTLS",
        "SMTP_USE_SSL",
        "SMTP_TIMEOUT_SECONDS",
    }
    assert required <= values.keys()
    assert values["ENVIRONMENT"] == "production"
    assert values["JWT_ALGORITHM"] == "HS256"
    assert int(values["RATE_LIMIT_PER_MINUTE"]) > 0
    assert int(values["ACCESS_TOKEN_EXPIRE_MINUTES"]) > 0
    assert int(values["REFRESH_TOKEN_EXPIRE_DAYS"]) > 0
    assert int(values["PASSWORD_RESET_EXPIRE_MINUTES"]) >= 5

    origins = json.loads(values["CORS_ORIGINS"])
    assert origins == ["https://ideal-marcenaria.onrender.com"]
    assert values["FRONTEND_URL"] == origins[0]


def test_password_reset_token_uses_url_fragment():
    auth_source = (ROOT / "backend" / "app" / "api" / "auth.py").read_text(encoding="utf-8")
    frontend_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert '/#reset_token={token}' in auth_source
    assert "location.hash.slice(1)" in frontend_source


def test_frontend_keeps_cross_origin_csrf_token_in_memory():
    frontend_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "csrfToken:''" in frontend_source
    assert "if(data.csrf_token)state.csrfToken=data.csrf_token" in frontend_source
    assert "await api('/auth/csrf')" in frontend_source


def test_render_blueprint_keeps_readiness_probe_and_production_origin():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "healthCheckPath: /ready" in blueprint
    assert 'value: \'["https://ideal-marcenaria.onrender.com"]\'' in blueprint
    assert "value: https://ideal-marcenaria.onrender.com" in blueprint


def test_render_blueprint_matches_linked_production_resources():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {service["name"]: service for service in blueprint["services"]}
    databases = {database["name"]: database for database in blueprint["databases"]}

    assert set(services) == {
        "ideal-marcenaria-api",
        "ideal-marcenaria",
        "ideal-marcenaria-redis",
    }
    assert set(databases) == {"Ideal"}

    api_env = {entry["key"]: entry for entry in services["ideal-marcenaria-api"]["envVars"]}
    assert api_env["DATABASE_URL"]["fromDatabase"] == {
        "name": "Ideal",
        "property": "connectionString",
    }
    assert api_env["REDIS_URL"]["fromService"] == {
        "type": "keyvalue",
        "name": "ideal-marcenaria-redis",
        "property": "connectionString",
    }
