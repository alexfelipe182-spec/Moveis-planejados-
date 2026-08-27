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


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(protected_router)
api_router.include_router(admin_router)
api_router.include_router(activity_router)
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
    dependencies=[Depends(get_current_user)],
)
def list_quotes(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return crud.list_items(db, Quote, offset=offset, limit=limit)


@quotes_router.post("", response_model=QuoteRead, status_code=201, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def create_quote(payload: QuoteCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    pricing = _quote_calculation(payload)
    analysis = analyze_quote(base_cost=pricing["base_cost"], suggested_total=pricing["suggested_total"], profit_margin=pricing["profit_margin"])
    data = payload.model_dump()
    data.update({"suggested_total": pricing["suggested_total"], "total": pricing["suggested_total"], "status": "analysis",
                 "ai_analysis": analysis["ai_analysis"], "ai_analyzed_at": analysis["ai_analyzed_at"]})
    try:
        item = crud.create_item(db, Quote(**data), commit=False)
        db.add(Activity(user_id=current_user.id, action="created", entity="quote", entity_id=item.id,
                        description=f"Criou quote #{item.id} com análise inteligente"))
        _commit_quote_write(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    engine.emit("quote.created", {"entity": "quote", "item_id": item.id, "user_id": current_user.id,
                                   "base_cost": pricing["base_cost"], "suggested_total": pricing["suggested_total"],
                                   "profit_margin": pricing["profit_margin"]})
    return item


@quotes_router.post(
    "/estimate",
    response_model=QuoteEstimateResponse,
    dependencies=[Depends(require_admin)],
)
def estimate_quote(payload: QuoteEstimateRequest):
    pricing = calculate_quote_suggestion(**payload.model_dump())
    return analyze_quote(base_cost=pricing["base_cost"], suggested_total=pricing["suggested_total"],
                         profit_margin=pricing["profit_margin"]) | pricing


@quotes_router.put("/{item_id}", response_model=QuoteRead, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def update_quote(item_id: int, payload: QuoteUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Atualiza dados técnicos antes da decisão; transições de status usam endpoints dedicados."""
    item = crud.get_item(db, Quote, item_id)
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
    data = payload.model_dump(exclude_unset=True, exclude={"status"})
    pricing = _quote_calculation(payload, item)
    analysis = analyze_quote(base_cost=pricing["base_cost"], suggested_total=pricing["suggested_total"], profit_margin=pricing["profit_margin"])
    data.update({"suggested_total": pricing["suggested_total"], "total": pricing["suggested_total"],
                 "status": "analysis",
                 "ai_analysis": analysis["ai_analysis"], "ai_analyzed_at": analysis["ai_analyzed_at"]})
    try:
        item = crud.update_item(db, item, data, commit=False)
        db.add(Activity(user_id=current_user.id, action="updated", entity="quote", entity_id=item.id,
                        description=f"Atualizou quote #{item.id} e recalculou análise inteligente"))
        _commit_quote_write(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    engine.emit("quote.updated", {"entity": "quote", "item_id": item.id, "user_id": current_user.id,
                                   "suggested_total": pricing["suggested_total"], "profit_margin": pricing["profit_margin"]})
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
