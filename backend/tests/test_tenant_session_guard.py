from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Activity,
    Category,
    Customer,
    Material,
    Product,
    Project,
    ProjectCost,
    Quote,
    QuoteItem,
    Supplier,
    Tenant,
    User,
)
from app.models.tenant import TenantScopedMixin


@pytest.fixture
def tenant_database():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed_tenants(factory):
    setup = factory()
    tenant_a = Tenant(name="Marcenaria A", slug="marcenaria-a")
    tenant_b = Tenant(name="Marcenaria B", slug="marcenaria-b")
    setup.add_all([tenant_a, tenant_b])
    setup.commit()
    setup.close()

    a = factory(info={"tenant_id": tenant_a.id})
    user_a = User(
        tenant_id=tenant_a.id,
        name="Administrador A",
        email="admin-a@example.com",
        password_hash="not-a-real-password",
    )
    customer_a = Customer(name="Cliente A")
    category_a = Category(name="Armários")
    supplier_a = Supplier(name="Fornecedor A")
    a.add_all([user_a, customer_a, category_a, supplier_a])
    a.flush()
    quote_a = Quote(customer_id=customer_a.id, description="Orçamento A")
    material_a = Material(
        supplier_id=supplier_a.id,
        name="MDF branco",
        kind="mdf",
        unit="chapa",
        unit_cost=Decimal("180"),
    )
    a.add_all([quote_a, material_a])
    a.flush()
    project_a = Project(
        customer_id=customer_a.id,
        quote_id=quote_a.id,
        name="Projeto A",
    )
    a.add(project_a)
    a.commit()
    ids = {
        "tenant_a": tenant_a.id,
        "tenant_b": tenant_b.id,
        "user_a": user_a.id,
        "customer_a": customer_a.id,
        "category_a": category_a.id,
        "supplier_a": supplier_a.id,
        "quote_a": quote_a.id,
        "material_a": material_a.id,
        "project_a": project_a.id,
    }
    a.close()

    b = factory(info={"tenant_id": tenant_b.id})
    b.add_all(
        [
            User(
                tenant_id=tenant_b.id,
                name="Administrador B",
                email="admin-b@example.com",
                password_hash="not-a-real-password",
            ),
            Customer(name="Cliente B"),
        ]
    )
    b.commit()
    b.close()
    return ids


def test_every_business_record_model_is_tenant_scoped():
    expected = {
        "activities",
        "categories",
        "customers",
        "materials",
        "products",
        "project_costs",
        "projects",
        "quote_items",
        "quotes",
        "suppliers",
        "users",
    }
    actual = {
        mapper.local_table.name
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, TenantScopedMixin)
    }

    assert actual == expected


def test_loader_scope_hides_other_tenant_rows(tenant_database):
    ids = seed_tenants(tenant_database)
    b = tenant_database(info={"tenant_id": ids["tenant_b"]})

    customers = b.scalars(select(Customer).order_by(Customer.id)).all()

    assert [customer.name for customer in customers] == ["Cliente B"]
    assert b.get(Customer, ids["customer_a"]) is None
    b.close()


@pytest.mark.parametrize(
    "factory",
    [
        lambda ids: Quote(customer_id=ids["customer_a"], description="Invasão"),
        lambda ids: Project(customer_id=ids["customer_a"], name="Invasão"),
        lambda ids: Product(category_id=ids["category_a"], name="Invasão"),
        lambda ids: Material(
            supplier_id=ids["supplier_a"],
            name="Insumo invasor",
            kind="mdf",
            unit="chapa",
        ),
        lambda ids: QuoteItem(quote_id=ids["quote_a"], name="Item invasor"),
        lambda ids: ProjectCost(
            project_id=ids["project_a"],
            material_id=ids["material_a"],
            category="material",
            description="Custo invasor",
        ),
        lambda ids: Activity(
            user_id=ids["user_a"],
            action="cross_tenant",
            entity="test",
            description="Atividade invasora",
        ),
    ],
)
def test_cross_tenant_references_are_rejected_before_commit(tenant_database, factory):
    ids = seed_tenants(tenant_database)
    b = tenant_database(info={"tenant_id": ids["tenant_b"]})
    b.add(factory(ids))

    with pytest.raises(ValueError, match="pertence a outra marcenaria"):
        b.flush()

    b.rollback()
    b.close()
