from sqlalchemy import false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Activity, Category, Customer, Material, Product, Project, Quote, Supplier, User


# Explicit fields prevent searching credentials or internal tokens as new columns
# are added. Related names are searched in SQL, not only in the visible page.
SEARCH_FIELDS = {
    Supplier: ("name", "contact_name", "email", "phone", "notes"),
    Material: ("name", "kind", "unit"),
    Category: ("name", "description"),
    Customer: ("name", "email", "phone", "address"),
    Product: ("name", "description"),
    Project: ("name", "description", "measurements", "materials", "status"),
    Quote: ("description", "measurements", "materials", "status"),
    User: ("name", "email"),
    Activity: ("action", "entity", "description"),
}


def _text_matches(model, pattern: str):
    return [getattr(model, name).ilike(pattern, escape="\\") for name in SEARCH_FIELDS.get(model, ())]


def _list_filters(model, *, q: str | None = None, status: str | None = None, ids=None, filters=()):
    conditions = list(filters)
    if q and q.strip():
        query = q.strip()
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        matches = _text_matches(model, pattern)
        if query.isascii() and query.isdigit() and len(query) <= 18:
            matches.append(model.id == int(query))
        if model in (Quote, Project):
            matches.append(model.customer_id.in_(select(Customer.id).where(or_(*_text_matches(Customer, pattern)))))
        if model is Product:
            matches.append(Product.category_id.in_(select(Category.id).where(or_(*_text_matches(Category, pattern)))))
        if model is Material:
            matches.append(Material.supplier_id.in_(select(Supplier.id).where(or_(*_text_matches(Supplier, pattern)))))
        conditions.append(or_(*matches) if matches else false())
    if status:
        status_column = getattr(model, "status", None)
        conditions.append(status_column == status if status_column is not None else false())
    if ids is not None:
        conditions.append(model.id.in_(ids))
    return conditions


def list_items(db: Session, model, *, offset: int = 0, limit: int = 100, q=None, status=None, ids=None, filters=()):
    order = (Activity.created_at.desc(), Activity.id.desc()) if model is Activity else (model.id,)
    statement = (
        select(model)
        .where(*_list_filters(model, q=q, status=status, ids=ids, filters=filters))
        .order_by(*order)
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(statement).all()


def count_items(db: Session, model, *, q=None, status=None, ids=None, filters=()) -> int:
    statement = select(func.count()).select_from(model).where(
        *_list_filters(model, q=q, status=status, ids=ids, filters=filters)
    )
    return int(db.scalar(statement) or 0)


def pagination_headers(response, *, total: int, offset: int, limit: int) -> None:
    """Keep the existing JSON array contract while publishing page metadata."""
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page-Offset"] = str(offset)
    response.headers["X-Page-Limit"] = str(limit)


def get_item(db: Session, model, item_id: int):
    return db.get(model, item_id)


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
