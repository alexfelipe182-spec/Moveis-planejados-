import hashlib
import hmac
import time
from datetime import datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import commercial
from app.core.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import PasswordResetToken


@pytest.mark.parametrize("environment,mode", [("test", "live"), ("development", "live"), ("production", "test")])
def test_stripe_rejects_key_from_other_environment(monkeypatch, environment, mode):
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setenv("STRIPE_SECRET_KEY", f"sk_{mode}_mock_only")
    with pytest.raises(HTTPException) as error:
        commercial._stripe_secret()
    assert error.value.status_code == 503
    assert "mock_only" not in error.value.detail


@pytest.mark.parametrize("prefix", ["sk_test_", "rk_test_"])
def test_stripe_accepts_test_secret_and_restricted_keys(monkeypatch, prefix):
    monkeypatch.setenv("STRIPE_SECRET_KEY", prefix + "mock_only")
    assert commercial._stripe_secret() == prefix + "mock_only"


def test_webhook_invalid_unicode_signature_is_rejected_and_rotation_works(monkeypatch):
    secret = "mock-webhook-only"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    body = b'{}'
    timestamp = str(int(time.time()))
    with pytest.raises(HTTPException) as error:
        commercial._verify_stripe_signature(body, f"t={timestamp},v1=é")
    assert error.value.status_code == 400
    valid = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    commercial._verify_stripe_signature(body, f"t={timestamp},v1=old,v1={valid}")
    with pytest.raises(HTTPException) as error:
        commercial._verify_stripe_signature(b'{"changed":true}', f"t={timestamp},v1={valid}")
    assert error.value.status_code == 400


def test_external_http_transport_is_blocked():
    with pytest.raises(AssertionError, match="Real email and HTTP"):
        httpx.post("https://api.stripe.com/v1/checkout/sessions")


def test_password_reset_expiration_replacement_and_production_privacy(monkeypatch):
    email = f"reset-delivery-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register", json={
            "name": "Demonstração fictícia", "email": email, "password": "Senha-Forte-123!",
        }).status_code == 201
        first = client.post("/api/v1/auth/password-reset/request", json={"email": email}).json()["debug_token"]
        second = client.post("/api/v1/auth/password-reset/request", json={"email": email}).json()["debug_token"]
        assert first != second
        assert client.post("/api/v1/auth/password-reset/confirm", json={
            "token": first, "new_password": "Outra-Senha-123!",
        }).status_code == 400
        with SessionLocal() as db:
            record = db.query(PasswordResetToken).filter_by(token_hash=hashlib.sha256(second.encode()).hexdigest()).one()
            record.expires_at = datetime.now() - timedelta(minutes=1)
            db.commit()
        assert client.post("/api/v1/auth/password-reset/confirm", json={
            "token": second, "new_password": "Outra-Senha-123!",
        }).status_code == 400
        monkeypatch.setattr(settings, "environment", "production")
        known = client.post("/api/v1/auth/password-reset/request", json={"email": email})
        unknown = client.post("/api/v1/auth/password-reset/request", json={"email": f"missing-{uuid4().hex}@example.com"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        assert "debug_token" not in known.json()


def test_partial_customer_and_product_edits_preserve_saved_fields():
    email = f"crud-delivery-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        registered = client.post("/api/v1/auth/register-business", json={
            "business_name": "Marcenaria ficticia", "owner_name": "Responsavel ficticio",
            "email": email, "password": "Senha-Forte-123!",
        })
        assert registered.status_code == 201, registered.text
        assert client.post("/api/v1/auth/login", data={
            "username": email, "password": "Senha-Forte-123!",
        }).status_code == 200
        headers = {"X-CSRF-Token": client.cookies["csrf_token"]}
        customer = client.post("/api/v1/customers", headers=headers, json={
            "name": "Cliente ficticio", "email": email, "phone": "11999999999",
            "address": "Endereco demonstrativo",
        })
        assert customer.status_code == 201, customer.text
        customer_path = f"/api/v1/customers/{customer.json()['id']}"
        edited = client.put(customer_path, headers=headers, json={"name": "Cliente editado"})
        assert edited.status_code == 200, edited.text
        assert client.get(customer_path).json() == customer.json() | {"name": "Cliente editado"}
        cleared = client.put(customer_path, headers=headers, json={"phone": None})
        assert cleared.status_code == 200, cleared.text
        assert client.get(customer_path).json() == customer.json() | {"name": "Cliente editado", "phone": None}

        category = client.post("/api/v1/categories", headers=headers, json={"name": "Demonstracao"})
        assert category.status_code == 201, category.text
        product = client.post("/api/v1/products", headers=headers, json={
            "category_id": category.json()["id"], "name": "Armario ficticio",
            "description": "Produto demonstrativo", "price": "100.00", "is_active": True,
        })
        assert product.status_code == 201, product.text
        product_path = f"/api/v1/products/{product.json()['id']}"
        edited = client.put(product_path, headers=headers, json={"description": "Descricao editada"})
        assert edited.status_code == 200, edited.text
        assert client.get(product_path).json() == product.json() | {"description": "Descricao editada"}


def test_product_image_url_is_saved_and_can_be_cleared():
    email = f"image-delivery-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register-business", json={
            "business_name": "Marcenaria ficticia", "owner_name": "Responsavel ficticio",
            "email": email, "password": "Senha-Forte-123!",
        }).status_code == 201
        assert client.post("/api/v1/auth/login", data={
            "username": email, "password": "Senha-Forte-123!",
        }).status_code == 200
        headers = {"X-CSRF-Token": client.cookies["csrf_token"]}
        category = client.post("/api/v1/categories", headers=headers, json={"name": "Demonstracao"})
        assert category.status_code == 201
        product = client.post("/api/v1/products", headers=headers, json={
            "category_id": category.json()["id"], "name": "Armario ficticio", "price": "100.00",
            "image_url": "https://example.com/armario.png",
        })
        assert product.status_code == 201, product.text
        path = f"/api/v1/products/{product.json()['id']}"
        assert client.get(path).json()["image_url"] == "https://example.com/armario.png"
        changed = client.put(path, headers=headers, json={"image_url": "https://example.com/novo.png"})
        assert changed.status_code == 200, changed.text
        assert client.get(path).json()["image_url"] == "https://example.com/novo.png"
        cleared = client.put(path, headers=headers, json={"image_url": None})
        assert cleared.status_code == 200, cleared.text
        assert client.get(path).json()["image_url"] is None
