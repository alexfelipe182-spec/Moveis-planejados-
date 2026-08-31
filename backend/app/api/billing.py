import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Plan, Subscription, User
from app.schemas.billing import CheckoutRequest, PlanRead, SubscriptionRead
from app.services.billing import apply_webhook, checkout_session, subscription_allows_access, verify_webhook_signature

router = APIRouter(tags=["Billing"])


@router.get("/plans", response_model=list[PlanRead])
def list_plans(db: Session = Depends(get_db)):
    return db.scalars(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.monthly_price_cents, Plan.id)).all()


@router.get("/billing/subscription", response_model=SubscriptionRead, dependencies=[Depends(require_admin)])
def current_subscription(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.scalar(select(Subscription).where(Subscription.organization_id == current_user.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Assinatura não encontrada")
    return {
        "status": row.status,
        "provider": row.provider,
        "plan_code": row.plan.code,
        "plan_name": row.plan.name,
        "monthly_price_cents": row.plan.monthly_price_cents,
        "trial_end": row.trial_end,
        "current_period_end": row.current_period_end,
        "cancel_at_period_end": row.cancel_at_period_end,
        "access_allowed": subscription_allows_access(row),
    }


@router.post("/billing/checkout", dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    plan = db.scalar(select(Plan).where(Plan.code == payload.plan_code, Plan.is_active.is_(True)))
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    try:
        session = checkout_session(organization_id=current_user.organization_id, plan=plan)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Pagamento ainda não configurado") from exc
    return session


@router.post("/billing/webhooks/{provider}", status_code=status.HTTP_200_OK)
async def billing_webhook(
    provider: str,
    request: Request,
    x_billing_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if provider not in {"sandbox", "stripe"}:
        raise HTTPException(status_code=404, detail="Provedor não suportado")
    raw_body = await request.body()
    if not verify_webhook_signature(raw_body, x_billing_signature):
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
        created, result = apply_webhook(db, provider=provider, payload=payload, raw_body=raw_body)
    except (ValueError, json.JSONDecodeError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Webhook inválido") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Webhook já recebido ou conflito de dados") from exc
    return {"accepted": True, "duplicate": not created, "status": result}
