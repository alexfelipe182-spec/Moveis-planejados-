from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Customer, Project, Subscription, Tenant, UsageCounter, User


@dataclass(frozen=True)
class PlanDefinition:
    code: str
    name: str
    monthly_price_brl: int
    limits: dict[str, int | None]
    features: tuple[str, ...]


PLANS: dict[str, PlanDefinition] = {
    "starter": PlanDefinition(
        code="starter",
        name="Essencial",
        monthly_price_brl=149,
        limits={"users": 3, "customers": 250, "projects": 40, "quotes_month": 80, "ai_month": 60},
        features=("Clientes", "Orçamentos", "Projetos", "Dashboard", "IA assistida"),
    ),
    "professional": PlanDefinition(
        code="professional",
        name="Profissional",
        monthly_price_brl=299,
        limits={"users": 10, "customers": 2000, "projects": 250, "quotes_month": 500, "ai_month": 400},
        features=("Tudo do Essencial", "Equipe ampliada", "Produção", "Rentabilidade", "IA avançada"),
    ),
    "business": PlanDefinition(
        code="business",
        name="Empresa",
        monthly_price_brl=599,
        limits={"users": None, "customers": None, "projects": None, "quotes_month": None, "ai_month": None},
        features=("Tudo do Profissional", "Uso ilimitado", "Operação multi-equipe", "Prioridade comercial"),
    ),
}


def plan_for_tenant(tenant: Tenant) -> PlanDefinition:
    return PLANS.get(tenant.plan_code, PLANS["starter"])


def _period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def usage_quantity(db: Session, tenant_id: int, metric: str) -> int:
    period = _period()
    value = db.scalar(
        select(UsageCounter.quantity).where(
            UsageCounter.tenant_id == tenant_id,
            UsageCounter.metric == metric,
            UsageCounter.period == period,
        )
    )
    return int(value or 0)


def increment_usage(db: Session, tenant_id: int, metric: str, amount: int = 1) -> None:
    period = _period()
    counter = db.scalar(
        select(UsageCounter).where(
            UsageCounter.tenant_id == tenant_id,
            UsageCounter.metric == metric,
            UsageCounter.period == period,
        )
    )
    if counter is None:
        counter = UsageCounter(tenant_id=tenant_id, metric=metric, period=period, quantity=0)
        db.add(counter)
    counter.quantity += amount


def _current_resource_count(db: Session, tenant_id: int, metric: str) -> int:
    model = {"users": User, "customers": Customer, "projects": Project}.get(metric)
    if model is None:
        return usage_quantity(db, tenant_id, metric)
    query = select(func.count()).select_from(model)
    if model is User:
        query = query.where(User.tenant_id == tenant_id, User.is_active.is_(True))
    return int(db.scalar(query) or 0)


def ensure_capacity(db: Session, tenant: Tenant, metric: str, *, increment: int = 1) -> None:
    plan = plan_for_tenant(tenant)
    limit = plan.limits.get(metric)
    if limit is None:
        return
    current = _current_resource_count(db, tenant.id, metric)
    if current + increment > limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "plan_limit_reached",
                "metric": metric,
                "plan": plan.code,
                "limit": limit,
                "message": "Limite do plano atingido. Faça upgrade para continuar.",
            },
        )


def ensure_commercial_access(db: Session, tenant: Tenant) -> Subscription | None:
    subscription = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant.id))
    if subscription is None:
        return None
    if subscription.status in {"active", "trialing"}:
        return subscription
    raise HTTPException(
        status_code=402,
        detail={"code": "subscription_inactive", "status": subscription.status, "message": "Assinatura inativa."},
    )


def usage_snapshot(db: Session, tenant: Tenant) -> dict:
    plan = plan_for_tenant(tenant)
    return {
        "plan": plan.code,
        "limits": plan.limits,
        "usage": {
            "users": _current_resource_count(db, tenant.id, "users"),
            "customers": _current_resource_count(db, tenant.id, "customers"),
            "projects": _current_resource_count(db, tenant.id, "projects"),
            "quotes_month": usage_quantity(db, tenant.id, "quotes_month"),
            "ai_month": usage_quantity(db, tenant.id, "ai_month"),
        },
    }
