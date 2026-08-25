from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.activity import router as activity_router
from app.api.admin import router as admin_router
from app.api.crud_router import make_router
from app.api.customer_history import router as customer_history_router
from app.api.protected import router as protected_router
from app.models import Category, Customer, Product, Project, Quote
from app.schemas import (
    CategoryCreate, CategoryRead, CategoryUpdate,
    CustomerCreate, CustomerRead, CustomerUpdate,
    ProductCreate, ProductRead, ProductUpdate,
    ProjectCreate, ProjectRead, ProjectUpdate,
    QuoteCreate, QuoteRead, QuoteUpdate,
)
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
quotes_router.include_router(make_router(Quote, QuoteCreate, QuoteRead, QuoteUpdate, ""))


@quotes_router.post("/estimate", response_model=dict[str, object])
def estimate_quote(payload: QuoteEstimateRequest):
    """Calcula e analisa uma sugestão sem alterar o orçamento salvo."""
    pricing = calculate_quote_suggestion(**payload.model_dump())
    return analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
    ) | pricing


api_router.include_router(quotes_router)
