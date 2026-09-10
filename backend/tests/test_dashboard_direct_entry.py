from pathlib import Path
import sys

from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from frontend_server import app  # noqa: E402


client = TestClient(app)


def test_dashboard_route_injects_login_guard_only_for_dashboard() -> None:
    dashboard = client.get("/dashboard/")
    assert dashboard.status_code == 200
    assert '<script src="/dashboard-route-guard.js"></script>' in dashboard.text

    nested = client.get("/dashboard/clientes")
    assert nested.status_code == 200
    assert '<script src="/dashboard-route-guard.js"></script>' in nested.text

    public = client.get("/")
    assert public.status_code == 200
    assert '<script src="/dashboard-route-guard.js"></script>' not in public.text


def test_dashboard_login_guard_is_served_and_opens_login() -> None:
    response = client.get("/dashboard-route-guard.js")
    assert response.status_code == 200
    assert "isDashboardRoute" in response.text
    assert "openAuth('login')" in response.text
    assert "mm:auth-changed" in response.text
