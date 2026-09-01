from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Customer, Material, Tenant, User
from app.services.plans import ensure_capacity, increment_usage
from app.services.quote_brief import (
    CatalogMaterial,
    QuoteAIUnavailable,
    QuotePreview,
    build_quote_preview,
    extract_quote_brief,
)

router = APIRouter(prefix="/quotes", tags=["Quote AI Drafts"])


class QuoteDraftRequest(BaseModel):
    customer_id: int = Field(gt=0)
    request_text: str = Field(min_length=10, max_length=5000)
    profit_margin: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=5,
        decimal_places=2,
    )


def _tenant_for_user(db: Session, user: User) -> Tenant:
    tenant = db.get(Tenant, user.tenant_id) if user.tenant_id else None
    if tenant is None or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Marcenaria indisponível")
    return tenant


@router.post(
    "/draft",
    response_model=QuotePreview,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def create_quote_draft(
    payload: QuoteDraftRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Interpreta linguagem natural e precifica somente com o catálogo do tenant."""
    tenant = _tenant_for_user(db, current_user)
    ensure_capacity(db, tenant, "ai_month")
    customer = crud.get_item(db, Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    rows = (
        db.query(Material)
        .filter(Material.is_active.is_(True))
        .order_by(Material.name, Material.id)
        .limit(300)
        .all()
    )
    catalog = [
        CatalogMaterial(
            id=item.id,
            name=item.name,
            kind=item.kind,
            unit=item.unit,
            unit_cost=item.unit_cost,
            waste_percent=item.waste_percent,
        )
        for item in rows
    ]
    try:
        brief = extract_quote_brief(payload.request_text, catalog=catalog)
    except QuoteAIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    margin = payload.profit_margin
    if margin is None:
        margin = tenant.default_profit_margin
    preview = build_quote_preview(brief, catalog, profit_margin=margin)

    increment_usage(db, tenant.id, "ai_month")
    db.add(
        Activity(
            user_id=current_user.id,
            action="ai_quote_draft",
            entity="customer",
            entity_id=customer.id,
            description=f"Gerou prévia inteligente de orçamento para o cliente #{customer.id}",
        )
    )
    db.commit()
    return preview
