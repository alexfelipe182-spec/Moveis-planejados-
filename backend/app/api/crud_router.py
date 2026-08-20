from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user, require_csrf
from app.database import get_db


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

    @router.post("", response_model=read_schema, status_code=201, dependencies=[Depends(require_csrf)])
    def create(payload: create_schema, db: Session = Depends(get_db)):
        return crud.create_item(db, model(**payload.model_dump()))

    @router.put("/{item_id}", response_model=read_schema, dependencies=[Depends(require_csrf)])
    def update(item_id: int, payload: update_schema, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        return crud.update_item(db, item, payload.model_dump(exclude_unset=True))

    @router.delete("/{item_id}", status_code=204, dependencies=[Depends(require_csrf)])
    def delete(item_id: int, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        crud.delete_item(db, item)

    return router
