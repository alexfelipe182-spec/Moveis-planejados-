from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_MENU = ROOT / "frontend" / "account-menu-v2.js"
SAAS_PUBLIC = ROOT / "frontend" / "saas-public.js"


def test_settings_panel_loads_secure_integration_status():
    source = ACCOUNT_MENU.read_text(encoding="utf-8")

    assert "'/admin/integrations'" in source
    assert 'id="settings-integrations"' in source
    assert "Inteligência Artificial" in source
    assert "E-mail de recuperação" in source
    assert "Stripe" in source
    assert "Modo assistido" in source
    assert "fully_configured" in source


def test_integration_panel_never_renders_secret_fields():
    source = ACCOUNT_MENU.read_text(encoding="utf-8")

    forbidden = (
        "OPENAI_API_KEY",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "SMTP_PASSWORD",
    )
    assert all(value not in source for value in forbidden)


def test_account_menu_cache_version_is_bumped_for_integration_panel():
    source = SAAS_PUBLIC.read_text(encoding="utf-8")

    assert "account-menu-v2.js?v=20260907-4" in source
