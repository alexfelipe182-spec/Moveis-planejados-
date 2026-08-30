from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_cookie_csrf, require_superadmin
from app.database import get_db
from app.models import Customer, Project, Quote, Tenant, User
from app.schemas.tenant import SuperadminTenantUpdate, TenantRead, TenantUpdate
from app.services.plans import get_plan, public_plan_catalog
from app.tenancy import current_tenant

router = APIRouter(tags=["SaaS"])


@router.get("/plans")
def plans():
    return {"currency": "BRL", "plans": public_plan_catalog()}


@router.get("/tenant", response_model=TenantRead)
def get_my_tenant(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return current_tenant(db, current_user)


@router.patch("/tenant", response_model=TenantRead, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def update_my_tenant(payload: TenantUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    tenant = current_tenant(db, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, key, str(value) if key == "billing_email" and value is not None else value)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/superadmin/dashboard")
def superadmin_dashboard(_: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    return {"tenants": db.scalar(select(func.count()).select_from(Tenant)) or 0, "active_tenants": db.scalar(select(func.count()).select_from(Tenant).where(Tenant.status.in_(["trialing", "active", "past_due"]))) or 0, "users": db.scalar(select(func.count()).select_from(User)) or 0, "quotes": db.scalar(select(func.count()).select_from(Quote)) or 0, "projects": db.scalar(select(func.count()).select_from(Project)) or 0}


@router.get("/superadmin/tenants", response_model=list[TenantRead])
def list_tenants(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), _: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    return db.scalars(select(Tenant).order_by(Tenant.id).offset(offset).limit(limit)).all()


@router.get("/superadmin/tenants/{tenant_id}")
def get_tenant_summary(tenant_id: int, _: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    def count(model):
        return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id)) or 0
    return {"tenant": TenantRead.model_validate(tenant).model_dump(mode="json"), "counts": {"users": count(User), "customers": count(Customer), "quotes": count(Quote), "projects": count(Project)}}


@router.patch("/superadmin/tenants/{tenant_id}", response_model=TenantRead, dependencies=[Depends(require_superadmin), Depends(require_cookie_csrf)])
def update_tenant_by_superadmin(tenant_id: int, payload: SuperadminTenantUpdate, _: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    changes = payload.model_dump(exclude_unset=True)
    if "plan_code" in changes:
        get_plan(changes["plan_code"])
    for key, value in changes.items():
        setattr(tenant, key, value)
    db.commit()
    db.refresh(tenant)
    return tenant
