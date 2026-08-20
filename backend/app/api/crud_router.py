from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.database import get_db


def _database_conflict(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


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

    @router.post(
        "", response_model=read_schema, status_code=201,
        dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
    )
    def create(payload: create_schema, db: Session = Depends(get_db)):
        try:
            return crud.create_item(db, model(**payload.model_dump()))
        except ValueError as exc:
            raise _database_conflict(exc) from exc

    @router.put(
        "/{item_id}", response_model=read_schema,
        dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
    )
    def update(item_id: int, payload: update_schema, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        try:
            return crud.update_item(db, item, payload.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise _database_conflict(exc) from exc

    @router.delete(
        "/{item_id}", status_code=204,
        dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
    )
    def delete(item_id: int, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        try:
            crud.delete_item(db, item)
        except ValueError as exc:
            raise _database_conflict(exc) from exc

    return router
