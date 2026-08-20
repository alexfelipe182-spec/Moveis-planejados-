from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud


def make_router(model, create_schema, read_schema, update_schema, prefix: str):
    router = APIRouter(prefix=prefix, tags=[prefix.strip("/").capitalize()])
    @router.get("", response_model=list[read_schema])
    def list_all(db: Session = Depends(get_db)): return crud.list_items(db, model)
    @router.get("/{item_id}", response_model=read_schema)
    def get_one(item_id: int, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item: raise HTTPException(404, "Registro não encontrado")
        return item
    @router.post("", response_model=read_schema, status_code=201)
    def create(payload: create_schema, db: Session = Depends(get_db)):
        return crud.create_item(db, model(**payload.model_dump()))
    @router.put("/{item_id}", response_model=read_schema)
    def update(item_id: int, payload: update_schema, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item: raise HTTPException(404, "Registro não encontrado")
        return crud.update_item(db, item, payload.model_dump())
    @router.delete("/{item_id}", status_code=204)
    def delete(item_id: int, db: Session = Depends(get_db)):
        item = crud.get_item(db, model, item_id)
        if not item: raise HTTPException(404, "Registro não encontrado")
        crud.delete_item(db, item)
    return router
