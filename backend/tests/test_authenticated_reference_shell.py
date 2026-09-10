from pathlib import Path
import sys

from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from frontend_server import app  # noqa: E402


client = TestClient(app)


def test_index_injects_authenticated_reference_assets() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert '<link rel="stylesheet" href="/authenticated-reference.css">' in response.text
    assert '<script src="/authenticated-reference.js"></script>' in response.text
    assert '<script src="/dashboard-route-guard.js"></script>' not in response.text


def test_dashboard_keeps_login_guard_and_new_authenticated_shell() -> None:
    response = client.get("/dashboard/")

    assert response.status_code == 200
    assert '<link rel="stylesheet" href="/authenticated-reference.css">' in response.text
    assert '<script src="/authenticated-reference.js"></script>' in response.text
    assert '<script src="/dashboard-route-guard.js"></script>' in response.text


def test_authenticated_reference_assets_are_publicly_served() -> None:
    script = client.get("/authenticated-reference.js")
    style = client.get("/authenticated-reference.css")

    assert script.status_code == 200
    assert "reference-authenticated-dashboard" in script.text
    assert style.status_code == 200
    assert "reference-authenticated-dashboard" in style.text
