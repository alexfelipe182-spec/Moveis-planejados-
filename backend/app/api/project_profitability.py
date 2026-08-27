from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user
from app.database import get_db
from app.models import Project, ProjectCost, Quote

router = APIRouter(prefix="/projects", tags=["Project Profitability"])


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def _percent(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


@router.get(
    "/{project_id}/profitability",
    dependencies=[Depends(get_current_user)],
)
def project_profitability(project_id: int, db: Session = Depends(get_db)):
    project = crud.get_item(db, Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if project.quote_id is None:
        raise HTTPException(status_code=409, detail="Projeto ainda não está ligado a um orçamento vendido")

    quote = crud.get_item(db, Quote, project.quote_id)
    if not quote:
        raise HTTPException(status_code=409, detail="Orçamento vinculado ao projeto não foi encontrado")

    sold_total = Decimal(quote.total or 0)
    real_cost = Decimal(
        db.query(func.coalesce(func.sum(ProjectCost.total_cost), 0))
        .filter(ProjectCost.project_id == project_id)
        .scalar()
    )
    real_profit = sold_total - real_cost
    real_margin = (real_profit / sold_total * Decimal("100")) if sold_total > 0 else Decimal("0")

    expected_base_cost = Decimal(quote.material_cost or 0) + Decimal(quote.hardware_cost or 0) + Decimal(
        quote.labor_cost or 0
    ) + Decimal(quote.finishing_cost or 0)
    cost_variance = real_cost - expected_base_cost
    cost_variance_percent = (
        cost_variance / expected_base_cost * Decimal("100") if expected_base_cost > 0 else Decimal("0")
    )

    health = "healthy"
    if real_profit < 0:
        health = "loss"
    elif real_margin < Decimal("10"):
        health = "critical"
    elif real_margin < Decimal("20"):
        health = "attention"

    return {
        "project_id": project.id,
        "quote_id": quote.id,
        "sold_total": _money(sold_total),
        "expected_cost": _money(expected_base_cost),
        "real_cost": _money(real_cost),
        "real_profit": _money(real_profit),
        "real_margin_percent": _percent(real_margin),
        "cost_variance": _money(cost_variance),
        "cost_variance_percent": _percent(cost_variance_percent),
        "health": health,
    }
