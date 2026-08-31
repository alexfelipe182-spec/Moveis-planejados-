from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models import User
from app.services.automation import engine

router = APIRouter(prefix="/automations", tags=["Automations"])


@router.get("/results", dependencies=[Depends(require_admin)])
def automation_results(current_user: User = Depends(require_admin)):
    return engine.results_for_organization(current_user.organization_id)

