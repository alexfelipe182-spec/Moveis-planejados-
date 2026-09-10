import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

import pytest
from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from frontend_server import app  # noqa: E402
from scripts.serve_frontend import FrontendHandler  # noqa: E402


@pytest.fixture(params=["production", "development"])
def frontend_client(request):
    if request.param == "production":
        with TestClient(app) as client:
            yield lambda path, method="GET": client.request(method, path)
        return

    server = ThreadingHTTPServer(("127.0.0.1", 0), FrontendHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request_local(path, method="GET"):
        target = f"http://127.0.0.1:{server.server_port}{path}"
        req = UrlRequest(target, method=method)
        try:
            with urlopen(req, timeout=5) as response:
                return LocalResponse(response.status, dict(response.headers), response.read())
        except HTTPError as error:
            return LocalResponse(error.code, dict(error.headers), error.read())

    try:
        yield request_local
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class LocalResponse:
    def __init__(self, status_code, headers, content):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self):
        return self.content.decode("utf-8")


@pytest.mark.parametrize("path", ["/", "/dashboard/", "/clientes/42"])
def test_frontend_spa_routes_return_index(frontend_client, path):
    response = frontend_client(path)
    assert response.status_code == 200
    assert "Multi-Marcenarias" in response.text
    assert "notifications.js" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/assets/arquivo-ausente.png",
        "/api/v1/customers",
        "/notifications.test.cjs",
        "/.git/config",
    ],
)
def test_frontend_does_not_hide_real_404s_or_private_files(frontend_client, path):
    assert frontend_client(path).status_code == 404


def test_frontend_serves_existing_assets(frontend_client):
    response = frontend_client("/notifications.js")
    assert response.status_code == 200
    assert "mm-notifications-read" in response.text


def test_frontend_health_and_head(frontend_client):
    health = frontend_client("/health")
    head = frontend_client("/dashboard/", "HEAD")
    assert health.status_code == 200
    assert health.text == "ok"
    assert head.status_code == 200
    assert not head.content


def test_frontend_security_headers(frontend_client):
    response = frontend_client("/dashboard/")
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cache-control"] == "no-cache"
