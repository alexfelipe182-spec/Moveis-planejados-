from fastapi import APIRouter

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

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(protected_router)
api_router.include_router(admin_router)
api_router.include_router(activity_router)
api_router.include_router(customer_history_router)
api_router.include_router(make_router(Category, CategoryCreate, CategoryRead, CategoryUpdate, "/categories"))
api_router.include_router(make_router(Product, ProductCreate, ProductRead, ProductUpdate, "/products"))
api_router.include_router(make_router(Customer, CustomerCreate, CustomerRead, CustomerUpdate, "/customers"))
api_router.include_router(make_router(Project, ProjectCreate, ProjectRead, ProjectUpdate, "/projects"))
api_router.include_router(make_router(Quote, QuoteCreate, QuoteRead, QuoteUpdate, "/quotes"))
