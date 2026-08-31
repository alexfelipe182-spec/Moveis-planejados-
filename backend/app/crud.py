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


def _tenant_filter(model, organization_id: int | None):
    if organization_id is None:
        return ()
    organization_column = getattr(model, "organization_id", None)
    if organization_column is None:
        raise ValueError(f"{model.__name__} não declara ownership de organização")
    return (organization_column == organization_id,)


def _list_filters(
    model,
    *,
    q: str | None = None,
    status: str | None = None,
    ids=None,
    filters=(),
    organization_id: int | None = None,
):
    conditions = [*_tenant_filter(model, organization_id), *filters]
    if q and q.strip():
        query = q.strip()
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        matches = _text_matches(model, pattern)
        if query.isascii() and query.isdigit() and len(query) <= 18:
            matches.append(model.id == int(query))
        if model in (Quote, Project):
            customer_filters = [or_(*_text_matches(Customer, pattern))]
            if organization_id is not None:
                customer_filters.append(Customer.organization_id == organization_id)
            matches.append(model.customer_id.in_(select(Customer.id).where(*customer_filters)))
        if model is Product:
            category_filters = [or_(*_text_matches(Category, pattern))]
            if organization_id is not None:
                category_filters.append(Category.organization_id == organization_id)
            matches.append(Product.category_id.in_(select(Category.id).where(*category_filters)))
        if model is Material:
            supplier_filters = [or_(*_text_matches(Supplier, pattern))]
            if organization_id is not None:
                supplier_filters.append(Supplier.organization_id == organization_id)
            matches.append(Material.supplier_id.in_(select(Supplier.id).where(*supplier_filters)))
        conditions.append(or_(*matches) if matches else false())
    if status:
        status_column = getattr(model, "status", None)
        conditions.append(status_column == status if status_column is not None else false())
    if ids is not None:
        conditions.append(model.id.in_(ids))
    return conditions


def list_items(
    db: Session,
    model,
    *,
    offset: int = 0,
    limit: int = 100,
    q=None,
    status=None,
    ids=None,
    filters=(),
    organization_id: int | None = None,
):
    order = (Activity.created_at.desc(), Activity.id.desc()) if model is Activity else (model.id,)
    statement = (
        select(model)
        .where(
            *_list_filters(
                model,
                q=q,
                status=status,
                ids=ids,
                filters=filters,
                organization_id=organization_id,
            )
        )
        .order_by(*order)
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(statement).all()


def count_items(
    db: Session,
    model,
    *,
    q=None,
    status=None,
    ids=None,
    filters=(),
    organization_id: int | None = None,
) -> int:
    statement = select(func.count()).select_from(model).where(
        *_list_filters(
            model,
            q=q,
            status=status,
            ids=ids,
            filters=filters,
            organization_id=organization_id,
        )
    )
    return int(db.scalar(statement) or 0)


def pagination_headers(response, *, total: int, offset: int, limit: int) -> None:
    """Keep the existing JSON array contract while publishing page metadata."""
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page-Offset"] = str(offset)
    response.headers["X-Page-Limit"] = str(limit)


def get_item(db: Session, model, item_id: int, *, organization_id: int | None = None):
    if organization_id is None:
        return db.get(model, item_id)
    return db.scalar(
        select(model).where(
            model.id == item_id,
            *_tenant_filter(model, organization_id),
        )
    )


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
