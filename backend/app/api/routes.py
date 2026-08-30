from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.api.activity import router as activity_router
from app.api.admin import router as admin_router
from app.api.crud_router import make_router
from app.api.customer_history import router as customer_history_router
from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.api.production_costs import router as production_costs_router
from app.api.project_profitability import router as project_profitability_router
from app.api.project_workflow import router as project_workflow_router
from app.api.protected import router as protected_router
from app.api.quote_decisions import router as quote_decisions_router
from app.api.quote_intelligence import (
    build_quote_recommendation,
    router as quote_intelligence_router,
)
from app.api.quote_items import router as quote_items_router
from app.api.tenants import router as tenant_router
from app.database import get_db
from app.models import (
    Activity,
    Category,
    Customer,
    Material,
    Product,
    Project,
    Quote,
    Supplier,
    User,
)
from app.schemas import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    MaterialCreate,
    MaterialRead,
    MaterialUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    QuoteCreate,
    QuoteEstimateResponse,
    QuoteRead,
    QuoteUpdate,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
)
from app.services.automation import engine
from app.services.quote_ai import analyze_quote
from app.services.quote_pricing import calculate_quote_suggestion
from app.tenancy import tenant_get, tenant_query


class QuoteEstimateRequest(BaseModel):
    material_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    hardware_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    labor_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    finishing_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    profit_margin: Decimal = Field(
        default=30,
        ge=0,
        le=100,
        max_digits=5,
        decimal_places=2,
    )


api_router = APIRouter(prefix="/api/v1")
for child_router in [
    protected_router,
    tenant_router,
    admin_router,
    activity_router,
    customer_history_router,
]:
    api_router.include_router(child_router)
api_router.include_router(
    make_router(Category, CategoryCreate, CategoryRead, CategoryUpdate, "/categories")
)
api_router.include_router(
    make_router(
        Product,
        ProductCreate,
        ProductRead,
        ProductUpdate,
        "/products",
        tenant_links={"category_id": (Category, "Categoria")},
    )
)
api_router.include_router(
    make_router(Customer, CustomerCreate, CustomerRead, CustomerUpdate, "/customers")
)
api_router.include_router(
    make_router(Supplier, SupplierCreate, SupplierRead, SupplierUpdate, "/suppliers")
)
api_router.include_router(
    make_router(
        Material,
        MaterialCreate,
        MaterialRead,
        MaterialUpdate,
        "/materials",
        tenant_links={"supplier_id": (Supplier, "Fornecedor")},
    )
)
api_router.include_router(
    make_router(
        Project,
        ProjectCreate,
        ProjectRead,
        ProjectUpdate,
        "/projects",
        tenant_links={"customer_id": (Customer, "Cliente")},
    )
)
for child_router in [
    project_workflow_router,
    production_costs_router,
    project_profitability_router,
    quote_intelligence_router,
]:
    api_router.include_router(child_router)

quotes_router = APIRouter(prefix="/quotes", tags=["Quotes"])


def _quote_calculation(
    payload: QuoteCreate | QuoteUpdate,
    current: Quote | None = None,
):
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


def _commit_quote_write(db: Session, item: Quote) -> None:
    try:
        db.commit()
        db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Não foi possível concluir a alteração do orçamento",
        ) from exc


def _persist_intelligence(item: Quote, recommendation: dict) -> None:
    item.recommended_profit_margin = recommendation["recommended_margin_percent"]
    item.recommended_total = recommendation["recommended_total"]
    item.risk_score = recommendation["risk_score"]
    item.risk_level = recommendation["risk_level"]
    item.intelligence_confidence = recommendation["confidence"]
    item.intelligence_sample_size = recommendation["sample_size"]
    item.intelligence_analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)


@quotes_router.get(
    "",
    response_model=list[QuoteRead],
    dependencies=[Depends(get_current_user)],
)
def list_quotes(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        tenant_query(db, Quote, current_user)
        .order_by(Quote.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@quotes_router.post(
    "",
    response_model=QuoteRead,
    status_code=201,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def create_quote(
    payload: QuoteCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not tenant_get(db, Customer, payload.customer_id, current_user):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    pricing = _quote_calculation(payload)
    analysis = analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
    )
    recommendation = build_quote_recommendation(
        db,
        current_user,
        base_cost=pricing["base_cost"],
        requested_margin=pricing["profit_margin"],
    )
    data = payload.model_dump()
    data.update(
        {
            "tenant_id": current_user.tenant_id,
            "suggested_total": pricing["suggested_total"],
            "total": pricing["suggested_total"],
            "status": "analysis",
            "ai_analysis": analysis["ai_analysis"],
            "ai_analyzed_at": analysis["ai_analyzed_at"],
        }
    )
    try:
        item = crud.create_item(db, Quote(**data), commit=False)
        _persist_intelligence(item, recommendation)
        db.add(
            Activity(
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                action="created",
                entity="quote",
                entity_id=item.id,
                description=f"Criou quote #{item.id} com análise inteligente",
            )
        )
        _commit_quote_write(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    engine.emit(
        "quote.created",
        {
            "tenant_id": current_user.tenant_id,
            "entity": "quote",
            "item_id": item.id,
            "user_id": current_user.id,
            "base_cost": pricing["base_cost"],
            "suggested_total": pricing["suggested_total"],
            "profit_margin": pricing["profit_margin"],
            "risk_score": item.risk_score,
        },
    )
    return item


@quotes_router.post(
    "/estimate",
    response_model=QuoteEstimateResponse,
    dependencies=[Depends(require_admin)],
)
def estimate_quote(payload: QuoteEstimateRequest):
    pricing = calculate_quote_suggestion(**payload.model_dump())
    return analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
    ) | pricing


@quotes_router.put(
    "/{item_id}",
    response_model=QuoteRead,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def update_quote(
    item_id: int,
    payload: QuoteUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = tenant_get(db, Quote, item_id, current_user)
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
            detail=(
                "Orçamento com decisão registrada não pode ser alterado; "
                "crie uma nova revisão"
            ),
        )
    data = payload.model_dump(exclude_unset=True, exclude={"status"})
    if "customer_id" in data and not tenant_get(
        db,
        Customer,
        data["customer_id"],
        current_user,
    ):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    pricing = _quote_calculation(payload, item)
    analysis = analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
    )
    recommendation = build_quote_recommendation(
        db,
        current_user,
        base_cost=pricing["base_cost"],
        requested_margin=pricing["profit_margin"],
    )
    data.update(
        {
            "suggested_total": pricing["suggested_total"],
            "total": pricing["suggested_total"],
            "status": "analysis",
            "ai_analysis": analysis["ai_analysis"],
            "ai_analyzed_at": analysis["ai_analyzed_at"],
        }
    )
    try:
        item = crud.update_item(db, item, data, commit=False)
        _persist_intelligence(item, recommendation)
        db.add(
            Activity(
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                action="updated",
                entity="quote",
                entity_id=item.id,
                description=(
                    f"Atualizou quote #{item.id} e recalculou análise inteligente"
                ),
            )
        )
        _commit_quote_write(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    engine.emit(
        "quote.updated",
        {
            "tenant_id": current_user.tenant_id,
            "entity": "quote",
            "item_id": item.id,
            "user_id": current_user.id,
            "suggested_total": pricing["suggested_total"],
            "profit_margin": pricing["profit_margin"],
            "risk_score": item.risk_score,
        },
    )
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
