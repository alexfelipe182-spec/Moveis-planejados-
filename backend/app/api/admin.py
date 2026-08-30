from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_cookie_csrf
from app.core.config import settings
from app.core.security import hash_password
from app.database import get_db
from app.models import Activity, Category, Customer, Product, Project, Quote, User
from app.schemas.activity import ActivityRead
from app.schemas.tenant import TenantUserCreate
from app.schemas.user import UserRead, UserUpdate
from app.services.plans import get_plan
from app.tenancy import current_tenant

router = APIRouter(prefix="/admin", tags=["Administration"])


def _count(db: Session, model, tenant_id: int) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id)) or 0


@router.get("/dashboard")
def dashboard(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    tenant = current_tenant(db, current_user)
    recent = db.scalars(select(Activity).where(Activity.tenant_id == tenant.id).order_by(Activity.created_at.desc()).limit(10)).all()
    return {"app_name": settings.app_name, "tenant": {"id": tenant.id, "name": tenant.name, "plan_code": tenant.plan_code, "status": tenant.status}, "counts": {"users": _count(db, User, tenant.id), "categories": _count(db, Category, tenant.id), "products": _count(db, Product, tenant.id), "customers": _count(db, Customer, tenant.id), "quotes": _count(db, Quote, tenant.id), "projects": _count(db, Project, tenant.id)}, "recent_activities": [ActivityRead.model_validate(item).model_dump(mode="json") for item in recent]}


@router.get("/users", response_model=list[UserRead])
def list_users(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.tenant_id == current_user.tenant_id).order_by(User.id).offset(offset).limit(limit)).all()


@router.post("/users", response_model=UserRead, status_code=201, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def create_tenant_user(payload: TenantUserCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    tenant = current_tenant(db, current_user)
    plan = get_plan(tenant.plan_code)
    user_count = db.scalar(select(func.count()).select_from(User).where(User.tenant_id == tenant.id, User.is_active.is_(True))) or 0
    if user_count >= plan.max_users:
        raise HTTPException(status_code=409, detail=f"O plano {plan.name} permite até {plan.max_users} usuários ativos")
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    user = User(tenant_id=tenant.id, name=payload.name.strip(), email=email, password_hash=hash_password(payload.password), is_admin=payload.is_admin)
    db.add(user)
    db.flush()
    db.add(Activity(tenant_id=tenant.id, user_id=current_user.id, action="created", entity="user", entity_id=user.id, description=f"Adicionou usuário #{user.id} à empresa"))
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def update_user(user_id: int, payload: UserUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id))
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes:
        changes["email"] = str(changes["email"]).lower()
        existing = db.scalar(select(User).where(User.email == changes["email"], User.id != user.id))
        if existing:
            raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    if user.id == current_user.id and changes.get("is_admin") is False:
        raise HTTPException(status_code=400, detail="O administrador atual não pode remover a própria permissão")
    if user.id == current_user.id and changes.get("is_active") is False:
        raise HTTPException(status_code=400, detail="O administrador atual não pode desativar a própria conta")
    for key, value in changes.items():
        setattr(user, key, value)
    db.add(Activity(tenant_id=current_user.tenant_id, user_id=current_user.id, action="updated", entity="user", entity_id=user.id, description=f"Alterou usuário #{user.id}"))
    db.commit()
    db.refresh(user)
    return user
