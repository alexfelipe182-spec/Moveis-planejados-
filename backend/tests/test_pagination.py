"""Collection contract tests with an isolated database; no Redis/network needed."""

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import crud
from app.api.deps import get_current_user, require_admin
from app.api.routes import api_router
from app.database import Base, get_db
from app.models import Activity, Category, Customer, Product, Project, Quote, User


@pytest.fixture
def database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(Customer(id=index, name=f"Cliente {index:03}") for index in range(1, 136))
        db.add_all(Category(id=index, name=f"Serviço {index:03}") for index in range(1, 136))
        db.commit()
        yield db
    engine.dispose()


@pytest.fixture
def client(database):
    app = FastAPI()
    app.include_router(api_router)
    admin = User(id=1, name="Equipe", email="admin@example.com", is_admin=True, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("resource", ["customers", "categories"])
def test_array_contract_paginates_beyond_first_hundred(client, resource):
    response = client.get(f"/api/v1/{resource}?offset=100&limit=25")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == list(range(101, 126))
    assert response.headers["X-Total-Count"] == "135"
    assert response.headers["X-Page-Offset"] == "100"
    assert response.headers["X-Page-Limit"] == "25"
    last = client.get(f"/api/v1/{resource}?offset=125&limit=25")
    assert [item["id"] for item in last.json()] == list(range(126, 136))


def test_search_counts_and_pages_all_matching_records(client):
    response = client.get("/api/v1/customers", params={"q": "  CLIENTE 13  ", "limit": 2, "offset": 2})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [132, 133]
    assert response.headers["X-Total-Count"] == "6"


def test_exact_reference_lookup_does_not_truncate_to_first_hundred(client):
    response = client.get("/api/v1/customers?ids=131&ids=135&limit=100")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [131, 135]
    assert response.headers["X-Total-Count"] == "2"


@pytest.mark.parametrize("model,path", [(Quote, "quotes"), (Project, "projects")])
def test_search_includes_related_customer_and_status(database, client, model, path):
    database.get(Customer, 135).name = "Cliente fora da primeira página"
    extra = {"description": "Armário"} if model is Quote else {"name": "Armário"}
    database.add_all([
        model(id=1, customer_id=135, status="sent" if model is Quote else "planning", **extra),
        model(id=2, customer_id=135, status="accepted" if model is Quote else "completed", **extra),
        model(id=3, customer_id=1, status="sent" if model is Quote else "planning", **extra),
    ])
    database.commit()
    response = client.get(f"/api/v1/{path}", params={"q": "fora da primeira", "status": "sent" if model is Quote else "planning"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [1]
    assert response.headers["X-Total-Count"] == "1"


def test_product_search_includes_category(database, client):
    database.get(Category, 135).name = "Sob medida especial"
    database.add_all([Product(id=1, category_id=135, name="Mesa"), Product(id=2, category_id=1, name="Mesa")])
    database.commit()
    response = client.get("/api/v1/products?q=sob%20medida")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [1]


def test_search_wildcards_are_literal_and_sql_is_parameterized(database, client):
    database.add(Customer(name="Percentual 50%_oferta"))
    database.commit()
    response = client.get("/api/v1/customers", params={"q": "%_"})
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Percentual 50%_oferta"
    injected = client.get("/api/v1/customers", params={"q": "' OR 1=1 --"})
    assert injected.json() == []
    assert injected.headers["X-Total-Count"] == "0"


def test_numeric_id_search_is_exact(client):
    response = client.get("/api/v1/customers?q=135")
    assert [item["id"] for item in response.json()] == [135]


def test_user_search_never_queries_password_hash(database, client):
    database.add_all(User(id=index, name=f"Usuário {index}", email=f"person{index}@example.com", password_hash="internal-secret-hash") for index in range(1, 126))
    database.commit()
    page = client.get("/api/v1/admin/users?offset=100&limit=25")
    assert page.status_code == 200
    assert [item["id"] for item in page.json()] == list(range(101, 126))
    assert page.headers["X-Total-Count"] == "125"
    assert client.get("/api/v1/admin/users?q=internal-secret-hash").json() == []
    result = client.get("/api/v1/admin/users?q=person125")
    assert [item["id"] for item in result.json()] == [125]


@pytest.mark.parametrize("endpoint", ["/activities?entity=customer&entity_id=135&", "/customers/135/history?"])
def test_activity_history_paginates_deterministically_and_combines_filters(database, client, endpoint):
    timestamp = datetime(2026, 8, 27, 12, 0)
    database.add_all(Activity(id=index, action="updated", entity="customer", entity_id=135, description=f"Edição {index}", created_at=timestamp) for index in range(1, 126))
    database.add(Activity(id=126, action="created", entity="customer", entity_id=1, description="Edição fora do cliente", created_at=timestamp))
    database.commit()
    response = client.get(f"/api/v1{endpoint}offset=100&limit=25")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == list(range(25, 0, -1))
    assert response.headers["X-Total-Count"] == "125"
    result = client.get(f"/api/v1{endpoint}q=Edição%20125")
    assert [item["id"] for item in result.json()] == [125]
    assert result.headers["X-Total-Count"] == "1"


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 101}, {"q": "x" * 201}, {"ids": [1] * 101}])
def test_collection_inputs_are_bounded(client, params):
    assert client.get("/api/v1/customers", params=params).status_code == 422


def test_empty_out_of_range_page_keeps_total(client):
    response = client.get("/api/v1/customers?offset=999&limit=25")
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "135"


def test_unsupported_status_is_not_silently_ignored(database):
    assert crud.list_items(database, Customer, status="approved") == []
