from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, User
from app.services.automation import engine
from app.tenancy import ensure_tenant_reference, tenant_get, tenant_query


def _database_conflict(exc: ValueError | IntegrityError) -> HTTPException:
    detail = str(exc) if isinstance(exc, ValueError) else "Não foi possível concluir a operação no banco de dados"
    return HTTPException(status_code=409, detail=detail)


def _entity_name(model) -> str:
    return model.__tablename__.rstrip("s")


def _event_name(action: str, model) -> str:
    return f"{_entity_name(model)}.{action}"


def _log(db: Session, user: User, action: str, model, item_id: int | None, description: str) -> None:
    db.add(Activity(tenant_id=user.tenant_id, user_id=user.id, action=action, entity=_entity_name(model), entity_id=item_id, description=description))


def _emit(action: str, model, item_id: int, user: User) -> None:
    engine.emit(_event_name(action, model), {"tenant_id": user.tenant_id, "entity": _entity_name(model), "item_id": item_id, "user_id": user.id})


def _payload_data(payload, *, exclude_unset: bool = False) -> dict:
    data = payload.model_dump(exclude_unset=exclude_unset)
    if "photos" in data and data["photos"] is not None:
        data["photos"] = [str(photo) for photo in data["photos"]]
    data.pop("tenant_id", None)
    return data


def _validate_links(db: Session, user: User, data: dict, tenant_links: dict[str, tuple[type, str]]) -> None:
    for field, (related_model, label) in tenant_links.items():
        if field in data and data[field] is not None:
            ensure_tenant_reference(db, related_model, data[field], user, label)


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _database_conflict(exc) from exc


def make_router(model, create_schema, read_schema, update_schema, prefix: str, *, include_list: bool = True, include_create: bool = True, include_update: bool = True, include_delete: bool = True, tenant_links: dict[str, tuple[type, str]] | None = None):
    if prefix and not prefix.startswith("/"):
        raise ValueError("O prefixo do CRUD deve começar com '/'")
    if prefix.endswith("/"):
        raise ValueError("O prefixo do CRUD não deve terminar com '/'")
    tenant_links = tenant_links or {}
    router = APIRouter(prefix=prefix, tags=[prefix.strip("/").capitalize() or "Resource"], dependencies=[Depends(get_current_user)])
    collection_path = "" if prefix else "/"

    if include_list:
        @router.get(collection_path, response_model=list[read_schema])
        def list_all(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
            return tenant_query(db, model, current_user).order_by(model.id).offset(offset).limit(limit).all()

    @router.get("/{item_id}", response_model=read_schema)
    def get_one(item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        item = tenant_get(db, model, item_id, current_user)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        return item

    if include_create:
        @router.post(collection_path, response_model=read_schema, status_code=201, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
        def create(payload: create_schema, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
            data = _payload_data(payload)
            _validate_links(db, current_user, data, tenant_links)
            try:
                item = crud.create_item(db, model(tenant_id=current_user.tenant_id, **data), commit=False)
                _log(db, current_user, "created", model, item.id, f"Criou {_entity_name(model)} #{item.id}")
                _commit_or_conflict(db)
                db.refresh(item)
                _emit("created", model, item.id, current_user)
                return item
            except ValueError as exc:
                db.rollback()
                raise _database_conflict(exc) from exc

    if include_update:
        @router.put("/{item_id}", response_model=read_schema, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
        def update(item_id: int, payload: update_schema, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
            item = tenant_get(db, model, item_id, current_user)
            if not item:
                raise HTTPException(status_code=404, detail="Registro não encontrado")
            data = _payload_data(payload, exclude_unset=True)
            _validate_links(db, current_user, data, tenant_links)
            try:
                item = crud.update_item(db, item, data, commit=False)
                _log(db, current_user, "updated", model, item.id, f"Atualizou {_entity_name(model)} #{item.id}")
                _commit_or_conflict(db)
                db.refresh(item)
                _emit("updated", model, item.id, current_user)
                return item
            except ValueError as exc:
                db.rollback()
                raise _database_conflict(exc) from exc

    if include_delete:
        @router.delete("/{item_id}", status_code=204, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
        def delete(item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
            item = tenant_get(db, model, item_id, current_user)
            if not item:
                raise HTTPException(status_code=404, detail="Registro não encontrado")
            try:
                crud.delete_item(db, item, commit=False)
                _log(db, current_user, "deleted", model, item_id, f"Excluiu {_entity_name(model)} #{item_id}")
                _commit_or_conflict(db)
                _emit("deleted", model, item_id, current_user)
            except ValueError as exc:
                db.rollback()
                raise _database_conflict(exc) from exc

    return router
