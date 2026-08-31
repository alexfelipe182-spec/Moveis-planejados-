"""Behavioral security tests for organization data isolation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from app import crud
from app.api.auth import register
from app.api.crud_router import make_router
from app.api.deps import require_admin, require_cookie_csrf
from app.database import Base
from app.database import get_db
from app.models import Category, Customer, Organization, Product
from app.schemas import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.schemas.user import UserCreate


class TenantRecord(Base):
    __tablename__ = "test_tenant_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(80))


def test_crud_never_lists_counts_or_fetches_another_organization():
    """Catches a missing tenant predicate that would expose another marcenaria."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TenantRecord.__table__.create(engine)

    try:
        with Session(engine) as db:
            db.add_all(
                [
                    TenantRecord(id=1, organization_id=10, name="Cliente da Marcenaria A"),
                    TenantRecord(id=2, organization_id=20, name="Cliente da Marcenaria B"),
                ]
            )
            db.commit()

            visible = crud.list_items(db, TenantRecord, organization_id=10)

            assert [record.id for record in visible] == [1]
            assert crud.count_items(db, TenantRecord, organization_id=10) == 1
            assert crud.get_item(db, TenantRecord, 1, organization_id=10).name == "Cliente da Marcenaria A"
            assert crud.get_item(db, TenantRecord, 2, organization_id=10) is None
    finally:
        engine.dispose()


def test_customer_created_by_one_organization_is_invisible_to_another():
    """Catches tenant ownership missing from a real operational model."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database = Session(engine)
    active_user = {"value": type("UserContext", (), {"id": 1, "organization_id": 10})()}
    app = FastAPI()
    app.include_router(
        make_router(Customer, CustomerCreate, CustomerRead, CustomerUpdate, "/customers"),
        prefix="/api/v1",
    )
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[require_admin] = lambda: active_user["value"]
    app.dependency_overrides[require_cookie_csrf] = lambda: None

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            created = client.post("/api/v1/customers", json={"name": "Cliente exclusivo A"})
            assert created.status_code == 201, created.text

            active_user["value"] = type("UserContext", (), {"id": 2, "organization_id": 20})()
            assert client.get("/api/v1/customers").json() == []
            assert client.get(f"/api/v1/customers/{created.json()['id']}").status_code == 404
    finally:
        database.close()
        engine.dispose()


def test_every_operational_table_requires_organization_ownership():
    """Catches a table added to the SaaS without a mandatory tenant boundary."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    operational_tables = {
        "users",
        "activities",
        "categories",
        "customers",
        "products",
        "quotes",
        "quote_items",
        "projects",
        "suppliers",
        "materials",
        "project_costs",
    }

    try:
        database_schema = inspect(engine)
        for table in operational_tables:
            columns = {column["name"]: column for column in database_schema.get_columns(table)}
            assert "organization_id" in columns, f"{table} está sem ownership de tenant"
            assert columns["organization_id"]["nullable"] is False, f"{table}.organization_id aceita NULL"
    finally:
        engine.dispose()


def test_registration_atomically_creates_a_new_organization_owner():
    """Catches onboarding that creates a user without an isolated marcenaria or owner access."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            owner = register(
                UserCreate(
                    name="Maria da Oficina",
                    organization_name="Oficina Horizonte",
                    email="MARIA@EXAMPLE.COM",
                    password="Senha-Segura-123!",
                ),
                db,
            )
            organization = db.get(Organization, owner.organization_id)

            assert organization is not None
            assert organization.name == "Oficina Horizonte"
            assert organization.slug.startswith("oficina-horizonte")
            assert owner.email == "maria@example.com"
            assert owner.is_admin is True
            assert owner.organization_id == organization.id
    finally:
        engine.dispose()


def test_tenant_cannot_link_a_product_to_another_organizations_category():
    """Catches an IDOR through a foreign key that exists but belongs to another tenant."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database = Session(engine)
    database.add(Category(id=90, organization_id=20, name="Categoria privada B"))
    database.commit()
    active_user = type("UserContext", (), {"id": 1, "organization_id": 10})()
    app = FastAPI()
    app.include_router(
        make_router(Product, ProductCreate, ProductRead, ProductUpdate, "/products"),
        prefix="/api/v1",
    )
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[require_admin] = lambda: active_user
    app.dependency_overrides[require_cookie_csrf] = lambda: None

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/products",
                json={"category_id": 90, "name": "Produto invasor", "price": "100.00"},
            )
            assert response.status_code == 404
            assert database.query(Product).count() == 0
    finally:
        database.close()
        engine.dispose()


def test_database_composite_foreign_key_rejects_cross_tenant_reference():
    """The isolation boundary must survive direct SQL/imports, not only HTTP validation."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.commit()
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as database:
            database.add_all([
                Organization(id=10, name="A", slug="tenant-a"),
                Organization(id=20, name="B", slug="tenant-b"),
            ])
            database.commit()
            database.add(Category(id=91, organization_id=20, name="Privada B"))
            database.commit()
            database.add(Product(
                organization_id=10,
                category_id=91,
                name="Importação indevida",
                price=100,
            ))
            try:
                database.commit()
            except IntegrityError:
                database.rollback()
            else:
                raise AssertionError("a FK composta permitiu referência entre marcenarias")
    finally:
        engine.dispose()
