from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Response
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


def test_partial_update_preserves_unsupplied_fields():
    payload = UpdateSchema(name="Novo")
    assert crud_router._payload_data(payload, exclude_unset=True) == {"name": "Novo"}
    assert crud_router._payload_data(UpdateSchema(photos=[]), exclude_unset=True) == {"photos": []}
    assert crud_router._payload_data(UpdateSchema(photos=None), exclude_unset=True) == {"photos": None}


def test_list_and_get_success(monkeypatch):
    router = build_router()
    list_endpoint = endpoint_for(router, "GET")
    get_endpoint = endpoint_for(router, "GET", item=True)
    items = [SimpleNamespace(id=1, name="A"), SimpleNamespace(id=2, name="B")]

    monkeypatch.setattr(crud_router.crud, "list_items", lambda db, model, **kwargs: items)
    monkeypatch.setattr(crud_router.crud, "count_items", lambda db, model, **kwargs: len(items))
    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: items[0])

    response = Response()
    current_user = SimpleNamespace(id=1, organization_id=7)
    assert list_endpoint(response=response, offset=0, limit=100, current_user=current_user, db=object()) == items
    assert response.headers["X-Total-Count"] == "2"
    assert get_endpoint(item_id=1, current_user=current_user, db=object()) is items[0]


def test_crud_router_scopes_reads_and_assigns_writes_to_current_organization(monkeypatch):
    """Catches a route that forgets tenant scope or trusts organization input from the client."""
    router = build_router()
    list_endpoint = endpoint_for(router, "GET")
    get_endpoint = endpoint_for(router, "GET", item=True)
    create_endpoint = endpoint_for(router, "POST")
    current_user = SimpleNamespace(id=42, organization_id=7)
    observed = {"list": [], "count": [], "get": [], "create": []}
    created = SimpleNamespace(id=9, name="Novo", organization_id=7)
    db = MagicMock()

    monkeypatch.setattr(
        crud_router.crud,
        "list_items",
        lambda _db, _model, **kwargs: observed["list"].append(kwargs) or [],
    )
    monkeypatch.setattr(
        crud_router.crud,
        "count_items",
        lambda _db, _model, **kwargs: observed["count"].append(kwargs) or 0,
    )
    monkeypatch.setattr(
        crud_router.crud,
        "get_item",
        lambda _db, _model, item_id, **kwargs: observed["get"].append(kwargs) or created,
    )

    def create_item(_db, obj, *, commit=True):
        observed["create"].append(obj)
        return created

    monkeypatch.setattr(crud_router.crud, "create_item", create_item)
    monkeypatch.setattr(crud_router, "_log", lambda *args: None)
    monkeypatch.setattr(crud_router, "_emit", lambda *args: None)

    list_endpoint(response=Response(), offset=0, limit=100, current_user=current_user, db=db)
    get_endpoint(item_id=9, current_user=current_user, db=db)
    create_endpoint(payload=CreateSchema(name="Novo"), current_user=current_user, db=db)

    assert observed["list"][0]["organization_id"] == 7
    assert observed["count"][0]["organization_id"] == 7
    assert observed["get"][0]["organization_id"] == 7
    assert observed["create"][0].organization_id == 7


def test_get_one_returns_404_when_missing(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "GET", item=True)
    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        endpoint(item_id=123, current_user=SimpleNamespace(id=1, organization_id=7), db=object())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Registro não encontrado"


def test_create_success_logs_and_emits(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "POST")
    created = SimpleNamespace(id=7, name="Criado")
    logged = []
    emitted = []
    commits = []
    db = MagicMock()

    def create_item(_db, _obj, *, commit=True):
        commits.append(commit)
        return created

    monkeypatch.setattr(crud_router.crud, "create_item", create_item)
    monkeypatch.setattr(crud_router, "_log", lambda *args: logged.append(args))
    monkeypatch.setattr(crud_router, "_emit", lambda *args: emitted.append(args))

    result = endpoint(
        payload=CreateSchema(name="Criado"),
        current_user=SimpleNamespace(id=42, organization_id=7),
        db=db,
    )

    assert result is created
    assert commits == [False]
    assert logged
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(created)
    assert emitted == [("created", FakeModel, 7, 42, 7)]


def test_create_maps_value_error_to_409(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "POST")
    db = MagicMock()

    def fail_create(_db, _obj, *, commit=True):
        raise ValueError("duplicado")

    monkeypatch.setattr(crud_router.crud, "create_item", fail_create)

    with pytest.raises(HTTPException) as exc_info:
        endpoint(
            payload=CreateSchema(name="Duplicado"),
            current_user=SimpleNamespace(id=1, organization_id=7),
            db=db,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "duplicado"
    db.rollback.assert_called_once_with()


def test_update_success_logs_and_emits(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "PUT", item=True)
    existing = SimpleNamespace(id=10, name="Antigo")
    updated = SimpleNamespace(id=10, name="Novo")
    logged = []
    emitted = []
    commits = []
    db = MagicMock()

    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: existing)

    def update_item(_db, _item, _data, *, commit=True):
        commits.append(commit)
        return updated

    monkeypatch.setattr(crud_router.crud, "update_item", update_item)
    monkeypatch.setattr(crud_router, "_log", lambda *args: logged.append(args))
    monkeypatch.setattr(crud_router, "_emit", lambda *args: emitted.append(args))

    result = endpoint(
        item_id=10,
        payload=UpdateSchema(name="Novo"),
        current_user=SimpleNamespace(id=42, organization_id=7),
        db=db,
    )

    assert result is updated
    assert commits == [False]
    assert logged
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(updated)
    assert emitted == [("updated", FakeModel, 10, 42, 7)]


def test_update_handles_missing_and_conflict(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "PUT", item=True)

    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: None)
    with pytest.raises(HTTPException) as missing:
        endpoint(
            item_id=10,
            payload=UpdateSchema(name="Novo"),
            current_user=SimpleNamespace(id=1, organization_id=7),
            db=MagicMock(),
        )
    assert missing.value.status_code == 404

    existing = SimpleNamespace(id=10, name="Antigo")
    db = MagicMock()
    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: existing)

    def fail_update(_db, _item, _data, *, commit=True):
        raise ValueError("atualização inválida")

    monkeypatch.setattr(crud_router.crud, "update_item", fail_update)
    with pytest.raises(HTTPException) as conflict:
        endpoint(
            item_id=10,
            payload=UpdateSchema(name="Novo"),
            current_user=SimpleNamespace(id=1, organization_id=7),
            db=db,
        )
    assert conflict.value.status_code == 409
    assert conflict.value.detail == "atualização inválida"
    db.rollback.assert_called_once_with()


def test_delete_success_logs_and_emits(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "DELETE", item=True)
    existing = SimpleNamespace(id=20, name="Excluir")
    deleted = []
    logged = []
    emitted = []
    commits = []
    db = MagicMock()

    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: existing)

    def delete_item(_db, item, *, commit=True):
        commits.append(commit)
        deleted.append(item)

    monkeypatch.setattr(crud_router.crud, "delete_item", delete_item)
    monkeypatch.setattr(crud_router, "_log", lambda *args: logged.append(args))
    monkeypatch.setattr(crud_router, "_emit", lambda *args: emitted.append(args))

    result = endpoint(item_id=20, current_user=SimpleNamespace(id=42, organization_id=7), db=db)

    assert result is None
    assert commits == [False]
    assert deleted == [existing]
    assert logged
    db.commit.assert_called_once_with()
    assert emitted == [("deleted", FakeModel, 20, 42, 7)]


def test_delete_handles_missing_and_conflict(monkeypatch):
    router = build_router()
    endpoint = endpoint_for(router, "DELETE", item=True)

    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: None)
    with pytest.raises(HTTPException) as missing:
        endpoint(item_id=20, current_user=SimpleNamespace(id=1, organization_id=7), db=MagicMock())
    assert missing.value.status_code == 404

    existing = SimpleNamespace(id=20, name="Em uso")
    db = MagicMock()
    monkeypatch.setattr(crud_router.crud, "get_item", lambda db, model, item_id, **kwargs: existing)

    def fail_delete(_db, _item, *, commit=True):
        raise ValueError("registro em uso")

    monkeypatch.setattr(crud_router.crud, "delete_item", fail_delete)
    with pytest.raises(HTTPException) as conflict:
        endpoint(item_id=20, current_user=SimpleNamespace(id=1, organization_id=7), db=db)
    assert conflict.value.status_code == 409
    assert conflict.value.detail == "registro em uso"
    db.rollback.assert_called_once_with()
