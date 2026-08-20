from fastapi import APIRouter

from app.api.crud_router import make_router
from app.api.protected import router as protected_router
from app.models import Category, Customer, Product, Quote
from app.schemas import (
    CategoryCreate, CategoryRead, CategoryUpdate,
    CustomerCreate, CustomerRead, CustomerUpdate,
    ProductCreate, ProductRead, ProductUpdate,
    QuoteCreate, QuoteRead, QuoteUpdate,
)

# Prefixo comum para recursos protegidos e CRUD.
# A autenticação é registrada diretamente no app para deixar a rota
# /api/v1/auth/* explícita e evitar registros duplicados/ambíguos.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(protected_router)
api_router.include_router(make_router(Category, CategoryCreate, CategoryRead, CategoryUpdate, "/categories"))
api_router.include_router(make_router(Product, ProductCreate, ProductRead, ProductUpdate, "/products"))
api_router.include_router(make_router(Customer, CustomerCreate, CustomerRead, CustomerUpdate, "/customers"))
api_router.include_router(make_router(Quote, QuoteCreate, QuoteRead, QuoteUpdate, "/quotes"))
