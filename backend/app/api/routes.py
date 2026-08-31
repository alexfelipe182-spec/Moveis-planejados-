from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.api.activity import router as activity_router
from app.api.billing import router as billing_router
from app.api.automation import router as automation_router
from app.api.platform import router as platform_router
from app.api.onboarding import router as onboarding_router
from app.api.admin import router as admin_router
from app.api.crud_router import make_router
from app.api.customer_history import router as customer_history_router
from app.api.deps import require_admin, require_cookie_csrf, require_workspace_admin
from app.api.production_costs import router as production_costs_router
from app.api.project_profitability import router as project_profitability_router
from app.api.project_workflow import router as project_workflow_router
from app.api.protected import router as protected_router
from app.api.quote_decisions import router as quote_decisions_router
from app.api.quote_intelligence import build_quote_recommendation
from app.api.quote_intelligence import router as quote_intelligence_router
from app.api.quote_items import router as quote_items_router
from app.database import get_db
from app.models import Activity, Category, Customer, Material, Product, Project, Quote, Supplier, User
from app.schemas import (
    CategoryCreate, CategoryRead, CategoryUpdate,
    CustomerCreate, CustomerRead, CustomerUpdate,
    MaterialCreate, MaterialRead, MaterialUpdate,
    ProductCreate, ProductRead, ProductUpdate,
    ProjectCreate, ProjectRead, ProjectUpdate,
    QuoteCreate, QuoteEstimateResponse, QuoteRead, QuoteUpdate,
    SupplierCreate, SupplierRead, SupplierUpdate,
)
from app.services.automation import engine
from app.services.quote_ai import analyze_quote
from app.services.quote_pricing import calculate_quote_suggestion


class QuoteEstimateRequest(BaseModel):
    material_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    hardware_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    labor_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    finishing_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    profit_margin: Decimal = Field(default=30, ge=0, le=100, max_digits=5, decimal_places=2)
    description: str | None = Field(default=None, max_length=3000)
    measurements: str | None = Field(default=None, max_length=2000)
    materials: str | None = Field(default=None, max_length=2000)


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(protected_router)
api_router.include_router(admin_router)
api_router.include_router(activity_router)
api_router.include_router(billing_router)
api_router.include_router(automation_router)
api_router.include_router(platform_router)
api_router.include_router(onboarding_router)
api_router.include_router(customer_history_router)
api_router.include_router(make_router(Category, CategoryCreate, CategoryRead, CategoryUpdate, "/categories"))
api_router.include_router(make_router(Product, ProductCreate, ProductRead, ProductUpdate, "/products"))
api_router.include_router(make_router(Customer, CustomerCreate, CustomerRead, CustomerUpdate, "/customers"))
api_router.include_router(make_router(Supplier, SupplierCreate, SupplierRead, SupplierUpdate, "/suppliers"))
api_router.include_router(make_router(Material, MaterialCreate, MaterialRead, MaterialUpdate, "/materials"))
api_router.include_router(make_router(Project, ProjectCreate, ProjectRead, ProjectUpdate, "/projects"))
api_router.include_router(project_workflow_router)
api_router.include_router(production_costs_router)
api_router.include_router(project_profitability_router)
api_router.include_router(quote_intelligence_router)

quotes_router = APIRouter(prefix="/quotes", tags=["Quotes"])


def _quote_calculation(payload: QuoteCreate | QuoteUpdate, current: Quote | None = None):
    def value(name: str, default: Decimal = Decimal("0")) -> Decimal:
        supplied = getattr(payload, name, None)
        if supplied is not None:
            return supplied
        if current is not None:
            return getattr(current, name, default)
        return default

    return calculate_quote_suggestion(
        material_cost=value("material_cost"),
        hardware_cost=value("hardware_cost"),
        labor_cost=value("labor_cost"),
        finishing_cost=value("finishing_cost"),
        profit_margin=value("profit_margin", Decimal("30")),
    )


def _quote_context(payload: QuoteCreate | QuoteUpdate, current: Quote | None = None) -> dict[str, str | None]:
    def value(name: str) -> str | None:
        supplied = getattr(payload, name, None)
        if supplied is not None:
            return supplied
        return getattr(current, name, None) if current is not None else None

    return {name: value(name) for name in ("description", "measurements", "materials")}


def _quote_intelligence_fields(
    db: Session,
    organization_id: int,
    pricing: dict[str, Decimal],
) -> dict[str, object]:
    recommendation = build_quote_recommendation(
        db=db,
        organization_id=organization_id,
        base_cost=pricing["base_cost"],
        requested_margin=pricing["profit_margin"],
    )
    return {
        "recommended_profit_margin": recommendation["recommended_margin_percent"],
        "recommended_total": recommendation["recommended_total"],
        "risk_score": recommendation["risk_score"],
        "risk_level": recommendation["risk_level"],
        "intelligence_confidence": recommendation["confidence"],
        "intelligence_sample_size": recommendation["sample_size"],
        "intelligence_analyzed_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }


def _commit_quote_write(db: Session, item: Quote) -> None:
    try:
        db.commit()
        db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível concluir a alteração do orçamento") from exc


@quotes_router.get(
    "",
    response_model=list[QuoteRead],
    dependencies=[Depends(require_admin)],
)
def list_quotes(
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    q: Annotated[str | None, Query(max_length=200)] = None,
    status: Annotated[str | None, Query(max_length=30)] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    organization_id = current_user.organization_id
    total = crud.count_items(db, Quote, q=q, status=status, organization_id=organization_id)
    crud.pagination_headers(response, total=total, offset=offset, limit=limit)
    return crud.list_items(
        db,
        Quote,
        offset=offset,
        limit=limit,
        q=q,
        status=status,
        organization_id=organization_id,
    )


@quotes_router.post("", response_model=QuoteRead, status_code=201, dependencies=[Depends(require_workspace_admin), Depends(require_cookie_csrf)])
def create_quote(payload: QuoteCreate, current_user: User = Depends(require_workspace_admin), db: Session = Depends(get_db)):
    if not crud.get_item(db, Customer, payload.customer_id, organization_id=current_user.organization_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    pricing = _quote_calculation(payload)
    context = _quote_context(payload)
    analysis = analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
        **context,
    )
    data = payload.model_dump()
    data.update({"suggested_total": pricing["suggested_total"], "total": pricing["suggested_total"], "status": "analysis",
                 "ai_analysis": analysis["ai_analysis"], "ai_analyzed_at": analysis["ai_analyzed_at"]})
    data["organization_id"] = current_user.organization_id
    data.update(_quote_intelligence_fields(db, current_user.organization_id, pricing))
    try:
        item = crud.create_item(db, Quote(**data), commit=False)
        db.add(Activity(organization_id=current_user.organization_id, user_id=current_user.id, action="created", entity="quote", entity_id=item.id,
                        description=f"Criou quote #{item.id} com análise inteligente"))
        _commit_quote_write(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    engine.emit("quote.created", {"entity": "quote", "item_id": item.id, "user_id": current_user.id,
                                   "base_cost": pricing["base_cost"], "suggested_total": pricing["suggested_total"],
                                   "profit_margin": pricing["profit_margin"], "analysis": analysis,
                                   "organization_id": current_user.organization_id,
                                   "risk_score": item.risk_score, "risk_level": item.risk_level,
                                   "recommended_total": item.recommended_total, **context})
    return item


@quotes_router.post(
    "/estimate",
    response_model=QuoteEstimateResponse,
    dependencies=[Depends(require_workspace_admin)],
)
def estimate_quote(payload: QuoteEstimateRequest):
    pricing = calculate_quote_suggestion(**payload.model_dump(include={
        "material_cost", "hardware_cost", "labor_cost", "finishing_cost", "profit_margin",
    }))
    context = payload.model_dump(include={"description", "measurements", "materials"})
    return analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
        **context,
    ) | pricing


@quotes_router.put("/{item_id}", response_model=QuoteRead, dependencies=[Depends(require_workspace_admin), Depends(require_cookie_csrf)])
def update_quote(item_id: int, payload: QuoteUpdate, current_user: User = Depends(require_workspace_admin), db: Session = Depends(get_db)):
    """Atualiza dados técnicos antes da decisão; transições de status usam endpoints dedicados."""
    # Serialize edits with decisions and item updates, and re-read cached state
    # after waiting for the lock so an approval cannot be silently reopened.
    item = db.query(Quote).filter(
        Quote.id == item_id,
        Quote.organization_id == current_user.organization_id,
    ).with_for_update().populate_existing().one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if payload.status is not None:
        raise HTTPException(
            status_code=409,
            detail="Status do orçamento só pode ser alterado pelos fluxos de decisão e comercial",
        )
    if item.status not in {"pending", "analysis"}:
        raise HTTPException(
            status_code=409,
            detail="Orçamento com decisão registrada não pode ser alterado; crie uma nova revisão",
        )
    target_customer_id = payload.customer_id if payload.customer_id is not None else item.customer_id
    if not crud.get_item(db, Customer, target_customer_id, organization_id=current_user.organization_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    data = payload.model_dump(exclude_unset=True, exclude={"status"})
    pricing = _quote_calculation(payload, item)
    context = _quote_context(payload, item)
    analysis = analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
        **context,
    )
    data.update({"suggested_total": pricing["suggested_total"], "total": pricing["suggested_total"],
                 "status": "analysis",
                 "ai_analysis": analysis["ai_analysis"], "ai_analyzed_at": analysis["ai_analyzed_at"]})
    data.update(_quote_intelligence_fields(db, current_user.organization_id, pricing))
    try:
        item = crud.update_item(db, item, data, commit=False)
        db.add(Activity(organization_id=current_user.organization_id, user_id=current_user.id, action="updated", entity="quote", entity_id=item.id,
                        description=f"Atualizou quote #{item.id} e recalculou análise inteligente"))
        _commit_quote_write(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    engine.emit("quote.updated", {"entity": "quote", "item_id": item.id, "user_id": current_user.id,
                                   "suggested_total": pricing["suggested_total"], "profit_margin": pricing["profit_margin"],
                                   "organization_id": current_user.organization_id,
                                   "risk_score": item.risk_score, "risk_level": item.risk_level,
                                   "recommended_total": item.recommended_total})
    return item


quotes_router.include_router(
    make_router(
        Quote,
        QuoteCreate,
        QuoteRead,
        QuoteUpdate,
        "",
        include_list=False,
        include_create=False,
        include_update=False,
    )
)
api_router.include_router(quotes_router)
api_router.include_router(quote_decisions_router)
api_router.include_router(quote_items_router)
