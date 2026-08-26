from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from app.api import crud_router


class FakeModel:
    __tablename__ = "widgets"

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class CreateSchema(BaseModel):
    name: str
    photos: list[str] | None = None


class UpdateSchema(BaseModel):
    name: str | None = None
    photos: list[str] | None = None


class ReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


def endpoint_for(router, method: str, *, item: bool = False):
    for route in router.routes:
        methods = getattr(route, "methods", set())
        path = getattr(route, "path", "")
        if method in methods and ("{item_id}" in path) is item:
            return route.endpoint
    raise AssertionError(f"Endpoint {method} item={item} não encontrado")


def build_router():
    return crud_router.make_router(
        FakeModel,
        CreateSchema,
        ReadSchema,
        UpdateSchema,
        "/widgets",
    )


def test_crud_router_validates_prefix():
    with pytest.raises(ValueError, match="começar com"):
        crud_router.make_router(FakeModel, CreateSchema, ReadSchema, UpdateSchema, "widgets")

    with pytest.raises(ValueError, match="terminar com"):
        crud_router.make_router(FakeModel, CreateSchema, ReadSchema, UpdateSchema, "/widgets/")


def test_database_conflict_preserves_message():
    error = crud_router._database_conflict(ValueError("conflito de dados"))
    assert error.status_code == 409
    assert error.detail == "conflito de dados"


def test_payload_data_normalizes_photos():
    payload = CreateSchema(name="Teste", photos=["https://example.com/a.jpg"])
    assert crud_router._payload_data(payload) == {
        "name": "Teste",
        "photos": ["https://example.com/a.jpg"],
    }


def test_get_one_returns_404_when_missing(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "GET", item=True)
    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id: None)

    with pytest.raises(HTTPException) as exc_info:
        endpoint(item_id=123, db=object())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Registro não encontrado"


def test_create_maps_value_error_to_409(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "POST")
    monkeypatch.setattr(
        crud_router.crud,
        "create_item",
        lambda db, obj: (_ for _ in ()).throw(ValueError("duplicado")),
    )

    with pytest.raises(HTTPException) as exc_info:
        endpoint(
            payload=CreateSchema(name="Duplicado"),
            current_user=SimpleNamespace(id=1),
            db=object(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "duplicado"


def test_update_handles_missing_and_conflict(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "PUT", item=True)

    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id: None)
    with pytest.raises(HTTPException) as missing:
        endpoint(
            item_id=10,
            payload=UpdateSchema(name="Novo"),
            current_user=SimpleNamespace(id=1),
            db=object(),
        )
    assert missing.value.status_code == 404

    existing = SimpleNamespace(id=10, name="Antigo")
    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id: existing)
    monkeypatch.setattr(
        crud_router.crud,
        "update_item",
        lambda db, item, data: (_ for _ in ()).throw(ValueError("atualização inválida")),
    )
    with pytest.raises(HTTPException) as conflict:
        endpoint(
            item_id=10,
            payload=UpdateSchema(name="Novo"),
            current_user=SimpleNamespace(id=1),
            db=object(),
        )
    assert conflict.value.status_code == 409
    assert conflict.value.detail == "atualização inválida"


def test_delete_handles_missing_and_conflict(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "DELETE", item=True)

    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id: None)
    with pytest.raises(HTTPException) as missing:
        endpoint(item_id=20, current_user=SimpleNamespace(id=1), db=object())
    assert missing.value.status_code == 404

    existing = SimpleNamespace(id=20, name="Em uso")
    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id: existing)
    monkeypatch.setattr(
        crud_router.crud,
        "delete_item",
        lambda db, item: (_ for _ in ()).throw(ValueError("registro em uso")),
    )
    with pytest.raises(HTTPException) as conflict:
        endpoint(item_id=20, current_user=SimpleNamespace(id=1), db=object())
    assert conflict.value.status_code == 409
    assert conflict.value.detail == "registro em uso"
