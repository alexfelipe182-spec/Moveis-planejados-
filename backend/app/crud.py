from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def list_items(db: Session, model, *, offset: int = 0, limit: int = 100):
    statement = select(model).offset(offset).limit(limit)
    return db.scalars(statement).all()


def get_item(db: Session, model, item_id: int):
    item = db.get(model, item_id)
    tenant_id = db.info.get("tenant_id")
    if tenant_id and item is not None and getattr(item, "tenant_id", tenant_id) != tenant_id:
        return None
    return item


def get_item_for_update(db: Session, model, item_id: int):
    return db.scalar(select(model).where(model.id == item_id).with_for_update().execution_options(populate_existing=True))


def create_item(db: Session, obj, *, commit: bool = True):
    try:
        db.add(obj)
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(obj)
        return obj
    except IntegrityError:
        db.rollback()
        raise ValueError("Não foi possível criar o registro: dados duplicados ou referência inválida") from None


def delete_item(db: Session, obj, *, commit: bool = True):
    try:
        db.delete(obj)
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError("Não foi possível excluir o registro porque ele está sendo utilizado") from None


def update_item(db: Session, obj, data: dict, *, commit: bool = True):
    for key, value in data.items():
        setattr(obj, key, value)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(obj)
        return obj
    except IntegrityError:
        db.rollback()
        raise ValueError("Não foi possível atualizar o registro: dados duplicados ou referência inválida") from None
