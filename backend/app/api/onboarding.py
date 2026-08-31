from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_cookie_csrf
from app.core.security import hash_password
from app.database import get_db
from app.models import Activity, Customer, Organization, Product, Project, Quote, Subscription, User
from app.schemas.user import UserRead
from app.services.billing import subscription_allows_access


class TeamMemberCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    is_admin: bool = False

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.get("/status", dependencies=[Depends(require_admin)])
def onboarding_status(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    organization = db.get(Organization, current_user.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Marcenaria não encontrada")
    subscription = db.scalar(select(Subscription).where(Subscription.organization_id == organization.id))
    access_allowed = subscription_allows_access(subscription)
    user_count = db.scalar(select(func.count()).select_from(User).where(User.organization_id == organization.id)) or 0
    first_customer = db.scalar(select(func.count()).select_from(Customer).where(Customer.organization_id == organization.id)) or 0
    first_product = db.scalar(select(func.count()).select_from(Product).where(Product.organization_id == organization.id)) or 0
    first_quote = db.scalar(select(func.count()).select_from(Quote).where(Quote.organization_id == organization.id)) or 0
    first_project = db.scalar(select(func.count()).select_from(Project).where(Project.organization_id == organization.id)) or 0
    checklist = [
        {"key": "organization", "complete": True},
        {"key": "owner", "complete": True},
        {"key": "subscription", "complete": subscription is not None and access_allowed},
        {"key": "first_customer", "complete": first_customer > 0},
        {"key": "first_product", "complete": first_product > 0},
        {"key": "first_quote", "complete": first_quote > 0},
        {"key": "first_project", "complete": first_project > 0},
    ]
    next_step = next((item["key"] for item in checklist if not item["complete"]), None)
    return {
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "status": organization.status,
        },
        "owner_user_id": current_user.id,
        "user_count": user_count,
        "subscription": {
            "status": subscription.status if subscription else None,
            "plan_id": subscription.plan_id if subscription else None,
            "access_allowed": access_allowed,
        },
        "checklist": checklist,
        "next_step": next_step,
    }


@router.post(
    "/members",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def add_team_member(
    payload: TeamMemberCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a member inside the current tenant, respecting its plan limit."""
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    subscription = db.scalar(select(Subscription).where(Subscription.organization_id == current_user.organization_id))
    if not subscription_allows_access(subscription):
        raise HTTPException(status_code=402, detail="A assinatura da marcenaria não está ativa")
    max_users = subscription.plan.max_users if subscription and subscription.plan else 3
    current_count = db.scalar(
        select(func.count()).select_from(User).where(User.organization_id == current_user.organization_id)
    ) or 0
    if current_count >= max_users:
        raise HTTPException(status_code=409, detail="Limite de usuários do plano atingido")
    member = User(
        organization_id=current_user.organization_id,
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(member)
    try:
        db.flush()
        db.add(Activity(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="created",
            entity="user",
            entity_id=member.id,
            description=f"Adicionou membro {member.email}",
        ))
        db.commit()
        db.refresh(member)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível criar o membro") from exc
    return member
