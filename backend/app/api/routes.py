from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud
from app.api.activity import router as activity_router
from app.api.admin import router as admin_router
from app.api.crud_router import make_router
from app.api.customer_history import router as customer_history_router
from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.api.protected import router as protected_router
from app.database import get_db
from app.models import Activity, Category, Customer, Product, Project, Quote, User
from app.schemas import (
    CategoryCreate, CategoryRead, CategoryUpdate,
    CustomerCreate, CustomerRead, CustomerUpdate,
    ProductCreate, ProductRead, ProductUpdate,
    ProjectCreate, ProjectRead, ProjectUpdate,
    QuoteCreate, QuoteRead, QuoteUpdate,
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
api_router.include_router(make_router(Project, ProjectCreate, ProjectRead, ProjectUpdate, "/projects"))

quotes_router = APIRouter(prefix="/quotes", tags=["Quotes"])


@quotes_router.post("", response_model=QuoteRead, status_code=201, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def create_quote(
    payload: QuoteCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Cria orçamento, calcula preço, executa análise e persiste o resultado."""
    pricing = calculate_quote_suggestion(
        material_cost=payload.material_cost,
        hardware_cost=payload.hardware_cost,
        labor_cost=payload.labor_cost,
        finishing_cost=payload.finishing_cost,
        profit_margin=payload.profit_margin,
    )
    analysis = analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
    )

    data = payload.model_dump()
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
        item = crud.create_item(db, Quote(**data))
        db.add(
            Activity(
                user_id=current_user.id,
                action="created",
                entity="quote",
                entity_id=item.id,
                description=f"Criou quote #{item.id} com análise inteligente",
            )
        )
        db.commit()
        db.refresh(item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    engine.emit(
        "quote.created",
        {
            "entity": "quote",
            "item_id": item.id,
            "user_id": current_user.id,
            "base_cost": pricing["base_cost"],
            "suggested_total": pricing["suggested_total"],
            "profit_margin": pricing["profit_margin"],
        },
    )
    return item


@quotes_router.post("/estimate", response_model=dict[str, object])
def estimate_quote(payload: QuoteEstimateRequest):
    """Calcula e analisa uma sugestão sem alterar o orçamento salvo."""
    pricing = calculate_quote_suggestion(**payload.model_dump())
    return analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
    ) | pricing


quotes_router.include_router(make_router(Quote, QuoteCreate, QuoteRead, QuoteUpdate, ""))
api_router.include_router(quotes_router)
