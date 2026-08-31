from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.core.config import settings
from app.database import get_db
from app.models import Subscription, Tenant, User
from app.services.plans import PLANS, usage_snapshot

router = APIRouter(tags=["SaaS Commercial"])


class CheckoutRequest(BaseModel):
    plan_code: str


class OnboardingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=40)
    document: str | None = Field(default=None, max_length=30)
    default_profit_margin: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    step: int | None = Field(default=None, ge=1, le=4)
    complete: bool = False


def _tenant(db: Session, user: User) -> Tenant:
    if not user.tenant_id:
        raise HTTPException(status_code=403, detail="Usuário sem marcenaria vinculada")
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Marcenaria não encontrada")
    return tenant


def _owner_emails() -> set[str]:
    raw = os.getenv("PLATFORM_OWNER_EMAILS", "")
    return {value.strip().lower() for value in raw.split(",") if value.strip()}


def _require_platform_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.email.lower() not in _owner_emails():
        raise HTTPException(status_code=403, detail="Acesso exclusivo do proprietário da plataforma")
    return current_user


def _stripe_price(plan_code: str) -> str | None:
    return os.getenv(f"STRIPE_PRICE_{plan_code.upper()}")


def _stripe_secret() -> str:
    value = os.getenv("STRIPE_SECRET_KEY")
    if not value:
        raise HTTPException(status_code=503, detail="Cobrança recorrente ainda não foi configurada no ambiente")
    return value


def _subscription_payload(subscription: Subscription | None, tenant: Tenant) -> dict:
    return {
        "tenant_id": tenant.id,
        "plan_code": tenant.plan_code,
        "subscription": None
        if subscription is None
        else {
            "provider": subscription.provider,
            "status": subscription.status,
            "plan_code": subscription.plan_code,
            "current_period_end": subscription.current_period_end,
            "trial_end": subscription.trial_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
        },
    }


def _onboarding_payload(tenant: Tenant) -> dict:
    return {
        "step": tenant.onboarding_step,
        "completed": tenant.onboarding_completed,
        "completed_at": tenant.onboarding_completed_at,
        "business": {
            "name": tenant.name,
            "phone": tenant.phone,
            "city": tenant.city,
            "state": tenant.state,
            "document": tenant.document,
            "default_profit_margin": tenant.default_profit_margin,
        },
        "checklist": {
            "business_profile": bool(tenant.name and tenant.phone and tenant.city and tenant.state),
            "pricing": tenant.default_profit_margin is not None,
            "team": True,
            "first_quote": False,
        },
    }


@router.get("/plans")
def plans():
    return [
        {
            "code": plan.code,
            "name": plan.name,
            "monthly_price_brl": plan.monthly_price_brl,
            "limits": plan.limits,
            "features": plan.features,
        }
        for plan in PLANS.values()
    ]


@router.get("/onboarding")
def onboarding_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _onboarding_payload(_tenant(db, current_user))


@router.patch("/onboarding", dependencies=[Depends(require_cookie_csrf)])
def update_onboarding(
    payload: OnboardingUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = _tenant(db, current_user)
    changes = payload.model_dump(exclude_unset=True, exclude={"step", "complete"})
    for key, value in changes.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(tenant, key, value)
    if payload.step is not None:
        tenant.onboarding_step = max(tenant.onboarding_step, payload.step)
    if payload.complete:
        required = [tenant.name, tenant.phone, tenant.city, tenant.state]
        if not all(required):
            raise HTTPException(status_code=409, detail="Complete os dados da marcenaria antes de finalizar o onboarding")
        tenant.onboarding_step = 4
        tenant.onboarding_completed = True
        tenant.onboarding_completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(tenant)
    return _onboarding_payload(tenant)


@router.get("/billing/subscription")
def subscription_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = _tenant(db, current_user)
    subscription = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant.id))
    return _subscription_payload(subscription, tenant) | {"usage": usage_snapshot(db, tenant)}


@router.post("/billing/checkout", dependencies=[Depends(require_cookie_csrf)])
def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if payload.plan_code not in PLANS:
        raise HTTPException(status_code=422, detail="Plano inválido")
    price_id = _stripe_price(payload.plan_code)
    if not price_id:
        raise HTTPException(status_code=503, detail="Preço recorrente não configurado para este plano")
    tenant = _tenant(db, current_user)
    secret = _stripe_secret()
    form = {
        "mode": "subscription",
        "success_url": f"{settings.frontend_url}/?billing=success",
        "cancel_url": f"{settings.frontend_url}/?billing=cancelled",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "client_reference_id": str(tenant.id),
        "customer_email": current_user.email,
        "metadata[tenant_id]": str(tenant.id),
        "metadata[plan_code]": payload.plan_code,
        "subscription_data[metadata][tenant_id]": str(tenant.id),
        "subscription_data[metadata][plan_code]": payload.plan_code,
    }
    try:
        response = httpx.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=form,
            headers={"Authorization": f"Bearer {secret}"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Falha ao iniciar cobrança recorrente") from exc
    data = response.json()
    return {"checkout_url": data.get("url"), "session_id": data.get("id")}


def _verify_stripe_signature(raw_body: bytes, signature: str | None) -> None:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret or not signature:
        raise HTTPException(status_code=400, detail="Webhook inválido")
    parts: dict[str, list[str]] = {}
    for item in signature.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts.setdefault(key, []).append(value)
    timestamp = parts.get("t", [None])[0]
    signatures = parts.get("v1", [])
    if timestamp is None or not signatures:
        raise HTTPException(status_code=400, detail="Assinatura de webhook inválida")
    try:
        if abs(time.time() - int(timestamp)) > 300:
            raise HTTPException(status_code=400, detail="Webhook expirado")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Timestamp de webhook inválido") from exc
    signed = timestamp.encode() + b"." + raw_body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise HTTPException(status_code=400, detail="Assinatura de webhook inválida")


def _unix_datetime(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)


def _upsert_subscription(db: Session, obj: dict) -> None:
    metadata = obj.get("metadata") or {}
    tenant_id = metadata.get("tenant_id")
    if not tenant_id:
        return
    tenant = db.get(Tenant, int(tenant_id))
    if tenant is None:
        return
    plan_code = metadata.get("plan_code") or tenant.plan_code
    if plan_code not in PLANS:
        plan_code = "starter"
    subscription = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant.id))
    if subscription is None:
        subscription = Subscription(tenant_id=tenant.id)
        db.add(subscription)
    subscription.provider = "stripe"
    subscription.provider_customer_id = obj.get("customer") or subscription.provider_customer_id
    subscription.provider_subscription_id = obj.get("id") or subscription.provider_subscription_id
    subscription.plan_code = plan_code
    subscription.status = obj.get("status") or subscription.status
    subscription.current_period_end = _unix_datetime(obj.get("current_period_end"))
    subscription.cancel_at_period_end = bool(obj.get("cancel_at_period_end", False))
    tenant.plan_code = plan_code
    tenant.is_active = subscription.status not in {"canceled", "unpaid", "incomplete_expired"}


@router.post("/billing/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    _verify_stripe_signature(raw_body, stripe_signature)
    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Webhook inválido") from exc
    event_type = event.get("type", "")
    obj = ((event.get("data") or {}).get("object") or {})
    if event_type.startswith("customer.subscription."):
        _upsert_subscription(db, obj)
        db.commit()
    return {"received": True}


@router.get("/platform/dashboard")
def platform_dashboard(
    _owner: User = Depends(_require_platform_owner),
    db: Session = Depends(get_db),
):
    tenants = db.scalars(select(Tenant).execution_options(skip_tenant_scope=True).order_by(Tenant.created_at.desc())).all()
    subscriptions = db.scalars(select(Subscription).execution_options(skip_tenant_scope=True)).all()
    status_counts: dict[str, int] = {}
    for subscription in subscriptions:
        status_counts[subscription.status] = status_counts.get(subscription.status, 0) + 1
    active_tenants = sum(1 for tenant in tenants if tenant.is_active)
    estimated_mrr = sum(PLANS.get(tenant.plan_code, PLANS["starter"]).monthly_price_brl for tenant in tenants if tenant.is_active)
    return {
        "tenants": len(tenants),
        "active_tenants": active_tenants,
        "subscriptions": len(subscriptions),
        "subscription_statuses": status_counts,
        "estimated_mrr_brl": estimated_mrr,
        "latest_tenants": [
            {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "plan_code": tenant.plan_code, "is_active": tenant.is_active}
            for tenant in tenants[:20]
        ],
    }


@router.get("/platform/metrics")
def platform_metrics(
    _owner: User = Depends(_require_platform_owner),
    db: Session = Depends(get_db),
):
    by_plan = dict(db.execute(select(Tenant.plan_code, func.count(Tenant.id)).group_by(Tenant.plan_code)).all())
    return {"tenants_by_plan": by_plan}
