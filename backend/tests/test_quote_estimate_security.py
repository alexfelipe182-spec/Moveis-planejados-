from fastapi.testclient import TestClient

from app.api.deps import require_admin
from app.database import SessionLocal
from app.main import app
from app.models import User


ESTIMATE_PAYLOAD = {
    "material_cost": "800.00",
    "hardware_cost": "350.00",
    "labor_cost": "900.00",
    "finishing_cost": "450.00",
    "profit_margin": "30.00",
}


def test_quote_listing_requires_authentication():
    client = TestClient(app)

    response = client.get("/api/v1/quotes")

    assert response.status_code == 401
    assert response.json()["detail"] == "Autenticação necessária"


def test_quote_estimate_requires_authentication():
    client = TestClient(app)

    response = client.post("/api/v1/quotes/estimate", json=ESTIMATE_PAYLOAD)

    assert response.status_code == 401
    assert response.json()["detail"] == "Autenticação necessária"


def test_quote_ai_draft_requires_authentication():
    client = TestClient(app)

    response = client.post(
        "/api/v1/quotes/draft",
        json={
            "customer_id": 1,
            "request_text": "Armário de três metros em MDF branco.",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Autenticação necessária"


def test_quote_estimate_rejects_non_admin_user():
    client = TestClient(app)
    email = "quote.estimate.user@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Quote Estimate User", "email": email, "password": password},
    )
    assert registered.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200

    response = client.post("/api/v1/quotes/estimate", json=ESTIMATE_PAYLOAD)

    assert response.status_code == 403
    assert response.json()["detail"] == "Acesso restrito ao administrador"


def test_quote_estimate_allows_admin_and_keeps_financial_values_locked():
    client = TestClient(app)
    email = "quote.estimate.admin@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Quote Estimate Admin", "email": email, "password": password},
    )
    assert registered.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/v1/quotes/estimate",
        json=ESTIMATE_PAYLOAD,
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["base_cost"] == "2500.00"
    assert body["suggested_total"] == "3250.00"
    assert body["profit_margin"] == "30.00"
    assert body["requires_approval"] is True


def test_quote_estimate_rejects_cookie_session_without_csrf_header():
    """Defect: a stolen cross-site cookie could trigger billable AI estimates."""
    app.dependency_overrides[require_admin] = lambda: object()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies.set("access_token", "cookie-session")

        response = client.post("/api/v1/quotes/estimate", json=ESTIMATE_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token inválido"


def test_quote_ai_draft_rejects_cookie_session_without_csrf_header():
    app.dependency_overrides[require_admin] = lambda: object()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies.set("access_token", "cookie-session")

        response = client.post(
            "/api/v1/quotes/draft",
            json={
                "customer_id": 1,
                "request_text": "Armário de três metros em MDF branco.",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token inválido"
