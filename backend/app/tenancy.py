import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Tenant, User

ACTIVE_TENANT_STATUSES = {"trialing", "active", "past_due"}


def current_tenant(db: Session, user: User) -> Tenant:
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=403, detail="Empresa vinculada ao usuário não foi encontrada")
    if tenant.status not in ACTIVE_TENANT_STATUSES:
        raise HTTPException(status_code=403, detail="A empresa está sem acesso ativo à plataforma")
    return tenant


def tenant_query(db: Session, model, user: User):
    current_tenant(db, user)
    if not hasattr(model, "tenant_id"):
        raise RuntimeError(f"{model.__name__} não é um recurso isolado por empresa")
    return db.query(model).filter(model.tenant_id == user.tenant_id)


def tenant_get(db: Session, model, item_id: int, user: User):
    return tenant_query(db, model, user).filter(model.id == item_id).one_or_none()


def ensure_tenant_reference(db: Session, model, item_id: int | None, user: User, label: str):
    if item_id is None:
        return None
    item = tenant_get(db, model, item_id, user)
    if not item:
        raise HTTPException(status_code=404, detail=f"{label} não encontrado")
    return item


def slug_base(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:100] or "marcenaria"


def unique_tenant_slug(db: Session, name: str) -> str:
    base = slug_base(name)
    candidate = base
    suffix = 2
    while db.query(Tenant.id).filter(Tenant.slug == candidate).first():
        candidate = f"{base[:95]}-{suffix}"
        suffix += 1
    return candidate
