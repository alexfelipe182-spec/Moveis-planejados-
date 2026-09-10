from pathlib import Path
import sys

from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from frontend_server import app  # noqa: E402


client = TestClient(app)


def test_session_controls_load_before_application_boot() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert '<script src="/session-controls.js"></script>' in response.text
    assert response.text.index('/session-controls.js') < response.text.index('./app.js')


def test_dashboard_also_receives_logout_hardening() -> None:
    response = client.get("/dashboard/")

    assert response.status_code == 200
    assert '<script src="/session-controls.js"></script>' in response.text
    assert '<script src="/dashboard-route-guard.js"></script>' in response.text


def test_session_controls_asset_contains_logout_race_protection() -> None:
    response = client.get("/session-controls.js")

    assert response.status_code == 200
    source = response.text
    assert "mm-explicit-signout" in source
    assert "abortRefreshRequests" in source
    assert "'/auth/refresh'" in source
    assert "'/me'" in source
    assert "window.location.replace('/')" in source
    assert "event.stopImmediatePropagation()" in source
    assert "button[onclick]:not([type])" in source
    assert "button.setAttribute('type', 'button')" in source
