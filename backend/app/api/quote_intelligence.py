from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models import Project, ProjectCost, Quote, User
from app.services.quote_intelligence import recommend_from_history
from app.tenancy import tenant_get, tenant_query

router = APIRouter(prefix="/quotes", tags=["Quote Intelligence"])


def _history(db: Session, current_user: User) -> tuple[list[Decimal], list[Decimal]]:
    historical_markups: list[Decimal] = []
    cost_variances: list[Decimal] = []
    projects = tenant_query(db, Project, current_user).filter(Project.quote_id.is_not(None), Project.status.in_(["delivered", "completed"])).all()
    for project in projects:
        quote = tenant_get(db, Quote, project.quote_id, current_user) if project.quote_id else None
        if not quote:
            continue
        sold_total = Decimal(quote.total or 0)
        real_cost = Decimal(db.query(func.coalesce(func.sum(ProjectCost.total_cost), 0)).filter(ProjectCost.tenant_id == current_user.tenant_id, ProjectCost.project_id == project.id).scalar())
        if real_cost <= 0:
            continue
        historical_markups.append((sold_total - real_cost) / real_cost * Decimal("100"))
        expected_cost = Decimal(quote.material_cost or 0) + Decimal(quote.hardware_cost or 0) + Decimal(quote.labor_cost or 0) + Decimal(quote.finishing_cost or 0)
        if expected_cost > 0:
            cost_variances.append((real_cost - expected_cost) / expected_cost * Decimal("100"))
    return historical_markups, cost_variances


def build_quote_recommendation(db: Session, current_user: User, *, base_cost: Decimal, requested_margin: Decimal):
    markups, variances = _history(db, current_user)
    return recommend_from_history(base_cost=base_cost, requested_margin=requested_margin, historical_margins=markups, historical_cost_variances=variances)


@router.get("/intelligence/recommendation")
def quote_recommendation(base_cost: Decimal, requested_margin: Decimal = Decimal("30"), current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return build_quote_recommendation(db, current_user, base_cost=base_cost, requested_margin=requested_margin)
