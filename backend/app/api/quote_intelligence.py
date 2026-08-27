from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models import Project, ProjectCost, Quote
from app.services.quote_intelligence import recommend_from_history

router = APIRouter(prefix="/quotes/intelligence", tags=["Quote Intelligence"])


class QuoteRecommendationRequest(BaseModel):
    material_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    hardware_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    labor_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    finishing_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    requested_margin: Decimal = Field(default=30, ge=0, le=80, max_digits=5, decimal_places=2)


def _pct(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _history(db: Session) -> tuple[list[Decimal], list[Decimal]]:
    margins: list[Decimal] = []
    variances: list[Decimal] = []

    projects = db.query(Project).filter(Project.quote_id.is_not(None)).all()
    for project in projects:
        quote = db.get(Quote, project.quote_id)
        if not quote:
            continue
        real_cost = Decimal(
            db.query(func.coalesce(func.sum(ProjectCost.total_cost), 0))
            .filter(ProjectCost.project_id == project.id)
            .scalar()
        )
        if real_cost <= 0:
            continue

        sold_total = Decimal(quote.total or 0)
        if sold_total <= 0:
            continue
        real_margin = (sold_total - real_cost) / sold_total * Decimal("100")

        expected_cost = (
            Decimal(quote.material_cost or 0)
            + Decimal(quote.hardware_cost or 0)
            + Decimal(quote.labor_cost or 0)
            + Decimal(quote.finishing_cost or 0)
        )
        variance = (
            (real_cost - expected_cost) / expected_cost * Decimal("100")
            if expected_cost > 0
            else Decimal("0")
        )
        margins.append(_pct(real_margin))
        variances.append(_pct(variance))

    return margins, variances


@router.post(
    "/recommend",
    dependencies=[Depends(require_admin)],
)
def recommend_quote(payload: QuoteRecommendationRequest, db: Session = Depends(get_db)):
    base_cost = (
        payload.material_cost
        + payload.hardware_cost
        + payload.labor_cost
        + payload.finishing_cost
    )
    margins, variances = _history(db)
    result = recommend_from_history(
        base_cost=base_cost,
        requested_margin=payload.requested_margin,
        historical_margins=margins,
        historical_cost_variances=variances,
    )
    return {
        "base_cost": format(base_cost, ".2f"),
        **{
            key: format(value, ".2f") if isinstance(value, Decimal) else value
            for key, value in result.items()
        },
    }
