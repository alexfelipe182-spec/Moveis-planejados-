from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Tenant, User
from app.schemas.tenant import TenantRead, TenantUpdate

router = APIRouter(prefix="/tenant", tags=["Tenant"])


def _tenant_for_user(db: Session, user: User) -> Tenant:
    if not user.tenant_id:
        raise HTTPException(status_code=403, detail="Usuário sem marcenaria vinculada")
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Marcenaria indisponível")
    return tenant


@router.get("", response_model=TenantRead)
def get_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _tenant_for_user(db, current_user)


@router.patch(
    "",
    response_model=TenantRead,
    dependencies=[Depends(require_cookie_csrf)],
)
def update_tenant(
    payload: TenantUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = _tenant_for_user(db, current_user)
    tenant.name = payload.name.strip()
    db.add(
        Activity(
            user_id=current_user.id,
            action="updated",
            entity="tenant",
            entity_id=tenant.id,
            description=f"Atualizou os dados da marcenaria #{tenant.id}",
        )
    )
    db.commit()
    db.refresh(tenant)
    return tenant
