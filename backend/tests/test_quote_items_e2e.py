from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Quote, User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    assert token, "CSRF cookie não foi criada após autenticação"
    return {"X-CSRF-Token": token}


def test_quote_items_crud_and_subtotal():
    client = TestClient(app, client=("quote-items-e2e", 50000))
    email = "quote.items.e2e@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Quote Items Admin", "email": email, "password": password},
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
    headers = csrf_headers(client)

    customer = client.post(
        "/api/v1/customers",
        json={"name": "Cliente Itens E2E"},
        headers=headers,
    )
    assert customer.status_code == 201

    quote = client.post(
        "/api/v1/quotes",
        json={"customer_id": customer.json()["id"], "description": "Orçamento com itens"},
        headers=headers,
    )
    assert quote.status_code == 201
    quote_id = quote.json()["id"]

    item = client.post(
        f"/api/v1/quotes/{quote_id}/items",
        json={
            "name": "Armário",
            "quantity": "2",
            "unit_price": "1250.00",
            "width": "2.40",
            "height": "2.10",
        },
        headers=headers,
    )
    assert item.status_code == 201, item.text
    assert item.json()["subtotal"] == "2500.00"

    db = SessionLocal()
    try:
        persisted_quote = db.get(Quote, quote_id)
        assert persisted_quote is not None
        assert persisted_quote.total == 2500
        assert persisted_quote.suggested_total == 2500
    finally:
        db.close()

    listed = client.get(f"/api/v1/quotes/{quote_id}/items")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.put(
        f"/api/v1/quotes/{quote_id}/items/{item.json()['id']}",
        json={"quantity": "3"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["subtotal"] == "3750.00"

    db = SessionLocal()
    try:
        persisted_quote = db.get(Quote, quote_id)
        assert persisted_quote is not None
        assert persisted_quote.total == 3750
        assert persisted_quote.suggested_total == 3750
    finally:
        db.close()

    deleted = client.delete(
        f"/api/v1/quotes/{quote_id}/items/{item.json()['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204

    remaining = client.get(f"/api/v1/quotes/{quote_id}/items")
    assert remaining.status_code == 200
    assert remaining.json() == []

    db = SessionLocal()
    try:
        persisted_quote = db.get(Quote, quote_id)
        assert persisted_quote is not None
        assert persisted_quote.total == 0
        assert persisted_quote.suggested_total == 0
    finally:
        db.close()
