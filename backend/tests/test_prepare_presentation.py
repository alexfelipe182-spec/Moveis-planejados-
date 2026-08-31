import json
from copy import deepcopy
from urllib.parse import parse_qs

import pytest

from prepare_presentation import NoRedirects, PreviewClient, prepare


def test_prepare_refuses_without_opt_in(monkeypatch):
    monkeypatch.delenv("IDEAL_LOCAL_PREVIEW", raising=False)
    client = PreviewClient()
    with pytest.raises(RuntimeError, match="IDEAL_LOCAL_PREVIEW"):
        client.verify()
    assert not client.verified


@pytest.mark.parametrize("missing", ["banner", "config"])
def test_prepare_checks_both_preview_markers(monkeypatch, missing):
    monkeypatch.setenv("IDEAL_LOCAL_PREVIEW", "1")
    client = PreviewClient()
    content = {
        "/": "AMBIENTE DE TESTE — dados sintéticos, sem envio de mensagens",
        "/site-config.js": "window.API_BASE_URL = window.location.origin + '/api/v1';",
    }
    content["/" if missing == "banner" else "/site-config.js"] = ""
    client.raw = lambda path: content[path]
    with pytest.raises(RuntimeError, match="nada foi gravado"):
        client.verify()
    assert not client.verified


def test_writes_are_blocked_before_preview_verification():
    with pytest.raises(RuntimeError, match="Confirme"):
        PreviewClient().raw("/api/v1/customers", "POST", {"name": "Não criar"})


def test_redirects_are_never_followed():
    with pytest.raises(RuntimeError, match="redirecionar"):
        NoRedirects().redirect_request(None, None, 302, "", {}, "https://example.com")


def test_login_uses_form_encoding_and_local_url():
    client = PreviewClient()
    client.verified = True
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"{}"

    class Opener:
        def open(self, req, timeout):
            requests.append(req)
            return Response()

    client.opener = Opener()
    payload = {"username": "preview@example.com", "password": "Preview-local-123!"}
    client.api("/auth/login", payload)
    request = requests[0]
    assert request.full_url == "http://127.0.0.1:8765/api/v1/auth/login"
    assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert parse_qs(request.data.decode()) == {key: [value] for key, value in payload.items()}


class MemoryPreview(PreviewClient):
    """No network; reuse the real ensure implementation against isolated dictionaries."""

    def __init__(self):
        self.data = {}
        self.created = 0

    def rows(self, path):
        if path.startswith("/project-costs/project/"):
            return self.data.get("/project-costs", [])
        return self.data.get(path, [])

    def api(self, path, payload=None):
        if payload is not None:
            rows = self.data.setdefault(path, [])
            item = {"id": len(rows) + 1, **deepcopy(payload)}
            rows.append(item)
            return item
        if path.endswith("/total"):
            return {"total_cost": "1260.00"}
        if path == "/quotes/1":
            return {**self.data["/quotes"][0], "total": "4200.00"}
        raise AssertionError(path)


def test_sample_is_repeatable_without_overwriting_or_duplicating_records():
    client = MemoryPreview()
    first = prepare(client)
    snapshot = deepcopy(client.data)
    second = prepare(client)
    assert first == second
    assert client.created == 10
    assert client.data == snapshot
    assert first["proposta"] == "4200.00"
    assert first["custos_registrados"] == "1260.00"
    # No real contact number is supplied by the fixture.
    assert "phone" not in json.dumps(client.data)


def test_changed_sample_is_preserved_not_reset():
    client = MemoryPreview()
    prepare(client)
    client.data["/materials"][0]["unit_cost"] = "999.00"
    snapshot = deepcopy(client.data)
    with pytest.raises(RuntimeError, match="preservados"):
        prepare(client)
    assert client.data == snapshot


def test_duplicate_sample_is_reported_without_deleting():
    client = MemoryPreview()
    prepare(client)
    client.data["/customers"].append(deepcopy(client.data["/customers"][0]))
    snapshot = deepcopy(client.data)
    with pytest.raises(RuntimeError, match="duplicados"):
        prepare(client)
    assert client.data == snapshot
