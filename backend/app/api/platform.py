from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Organization, Subscription, User

router = APIRouter(prefix="/platform", tags=["Platform Administration"])


@router.get("/overview", dependencies=[Depends(require_platform_admin)])
def platform_overview(db: Session = Depends(get_db)):
    """Return platform aggregates only; operational customer/quote content is never exposed."""
    return {
        "organizations": db.scalar(select(func.count()).select_from(Organization)) or 0,
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "subscriptions": db.scalar(select(func.count()).select_from(Subscription)) or 0,
        "subscription_statuses": {
            status: count
            for status, count in db.execute(
                select(Subscription.status, func.count()).group_by(Subscription.status)
            ).all()
        },
    }


@router.get("/organizations", dependencies=[Depends(require_platform_admin)])
def list_platform_organizations(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Organization, Subscription.status, Subscription.plan_id)
        .outerjoin(Subscription, Subscription.organization_id == Organization.id)
        .order_by(Organization.id)
    ).all()
    result = []
    for organization, subscription_status, plan_id in rows:
        user_count = db.scalar(select(func.count()).select_from(User).where(User.organization_id == organization.id)) or 0
        result.append({
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "status": organization.status,
            "subscription_status": subscription_status,
            "plan_id": plan_id,
            "user_count": user_count,
        })
    return result


@router.patch("/organizations/{organization_id}/status", dependencies=[Depends(require_platform_admin), Depends(require_cookie_csrf)])
def update_organization_status(
    organization_id: int,
    status: str,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    if status not in {"active", "suspended", "closed"}:
        raise HTTPException(status_code=422, detail="Status de organização inválido")
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    previous = organization.status
    organization.status = status
    db.add(Activity(
        organization_id=organization.id,
        user_id=current_user.id,
        action="platform_status_changed",
        entity="organization",
        entity_id=organization.id,
        description=f"Status da organização alterado: {previous} → {status}",
    ))
    db.commit()
    return {"id": organization.id, "status": organization.status}

