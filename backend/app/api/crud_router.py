from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, User


def _database_conflict(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def _entity_name(model) -> str:
    return model.__tablename__.rstrip("s")


def _log(db: Session, user: User, action: str, model, item_id: int | None, description: str) -> None:
    db.add(Activity(user_id=user.id, action=action, entity=_entity_name(model), entity_id=item_id, description=description))
    db.commit()


def make_router(model, create_schema, read_schema, update_schema, prefix: str):
    router = APIRouter(
        prefix=prefix,
        tags=[prefix.strip("/").capitalize()],
        dependencies=[Depends(get_current_user)],
    )

    @router.get("", response_model=list[read_schema])
    def list_all(
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        db: Session = Depends(get_db),
    ):
        return crud.list_items(db, model, offset=offset, limit=limit)

    @router.get("/{item_id}", response_model=read_schema)
    def get_one(item_id: int, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        return item

    @router.post("", response_model=read_schema, status_code=201, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
    def create(payload: create_schema, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
        try:
            item = crud.create_item(db, model(**payload.model_dump()))
            _log(db, current_user, "created", model, item.id, f"Criou {_entity_name(model)} #{item.id}")
            return item
        except ValueError as exc:
            raise _database_conflict(exc) from exc

    @router.put("/{item_id}", response_model=read_schema, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
    def update(item_id: int, payload: update_schema, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        try:
            item = crud.update_item(db, item, payload.model_dump(exclude_unset=True))
            _log(db, current_user, "updated", model, item.id, f"Atualizou {_entity_name(model)} #{item.id}")
            return item
        except ValueError as exc:
            raise _database_conflict(exc) from exc

    @router.delete("/{item_id}", status_code=204, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
    def delete(item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        try:
            crud.delete_item(db, item)
            _log(db, current_user, "deleted", model, item_id, f"Excluiu {_entity_name(model)} #{item_id}")
        except ValueError as exc:
            raise _database_conflict(exc) from exc

    return router
