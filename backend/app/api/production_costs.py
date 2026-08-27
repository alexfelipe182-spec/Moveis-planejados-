from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Material, Project, ProjectCost, User
from app.schemas.production_cost import ProjectCostCreate, ProjectCostRead
from app.services.automation import engine

router = APIRouter(prefix="/project-costs", tags=["Project Costs"])


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money_text(value: Decimal) -> str:
    return format(_money(value), ".2f")


@router.get(
    "/project/{project_id}",
    response_model=list[ProjectCostRead],
    dependencies=[Depends(get_current_user)],
)
def list_project_costs(project_id: int, db: Session = Depends(get_db)):
    if not crud.get_item(db, Project, project_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return db.query(ProjectCost).filter(ProjectCost.project_id == project_id).order_by(ProjectCost.id).all()


@router.get(
    "/project/{project_id}/total",
    dependencies=[Depends(get_current_user)],
)
def project_cost_total(project_id: int, db: Session = Depends(get_db)):
    if not crud.get_item(db, Project, project_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    total = db.query(func.coalesce(func.sum(ProjectCost.total_cost), 0)).filter(ProjectCost.project_id == project_id).scalar()
    return {"project_id": project_id, "total_cost": _money_text(Decimal(total))}


@router.post(
    "",
    response_model=ProjectCostRead,
    status_code=201,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def create_project_cost(
    payload: ProjectCostCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    project = crud.get_item(db, Project, payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    material = None
    unit_cost = payload.unit_cost
    if payload.material_id is not None:
        material = crud.get_item(db, Material, payload.material_id)
        if not material:
            raise HTTPException(status_code=404, detail="Insumo não encontrado")
        if unit_cost == 0:
            unit_cost = material.unit_cost

    quantity = payload.quantity
    waste_multiplier = Decimal("1")
    if material is not None and material.waste_percent:
        waste_multiplier += Decimal(material.waste_percent) / Decimal("100")
    total_cost = _money(quantity * unit_cost * waste_multiplier)

    item = ProjectCost(
        project_id=payload.project_id,
        material_id=payload.material_id,
        category=payload.category,
        description=payload.description,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
    )
    db.add(item)
    db.flush()
    db.add(
        Activity(
            user_id=current_user.id,
            action="cost_added",
            entity="project",
            entity_id=project.id,
            description=f"Adicionou custo de {total_cost} ao projeto #{project.id}: {payload.description}",
        )
    )
    db.commit()
    db.refresh(item)
    engine.emit(
        "project.cost_added",
        {
            "entity": "project",
            "item_id": project.id,
            "cost_id": item.id,
            "user_id": current_user.id,
            "total_cost": total_cost,
        },
    )
    return item
