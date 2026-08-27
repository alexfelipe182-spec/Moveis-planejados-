from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Project, User
from app.schemas.project import ProjectRead, ProjectStatus
from app.services.automation import engine

router = APIRouter(prefix="/projects", tags=["Projects"])


class ProjectStatusRequest(BaseModel):
    status: ProjectStatus


NEXT_STATUS = {
    "planning": "measurement",
    "measurement": "technical_design",
    "technical_design": "purchasing",
    "purchasing": "production",
    "production": "installation",
    "installation": "delivered",
    "delivered": "completed",
}

TERMINAL_STATUSES = {"completed", "cancelled"}


@router.patch(
    "/{item_id}/status",
    response_model=ProjectRead,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def advance_project_status(
    item_id: int,
    payload: ProjectStatusRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    project = crud.get_item(db, Project, item_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    previous_status = project.status
    requested_status = payload.status

    if previous_status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Projeto concluído ou cancelado não pode mudar de etapa")

    allowed_status = NEXT_STATUS.get(previous_status)
    is_cancel = requested_status == "cancelled"
    if not is_cancel and requested_status != allowed_status:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {previous_status} → {requested_status}. Próxima etapa: {allowed_status}",
        )

    project.status = requested_status
    db.add(
        Activity(
            user_id=current_user.id,
            action="status_changed",
            entity="project",
            entity_id=project.id,
            description=f"Alterou projeto #{project.id}: {previous_status} → {requested_status}",
        )
    )
    db.commit()
    db.refresh(project)

    engine.emit(
        "project.status_changed",
        {
            "entity": "project",
            "item_id": project.id,
            "user_id": current_user.id,
            "previous_status": previous_status,
            "status": requested_status,
            "quote_id": project.quote_id,
        },
    )
    return project
