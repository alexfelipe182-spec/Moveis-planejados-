import os
from collections import Counter

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models import User
from app.services.automation import engine

router = APIRouter(prefix="/automations", tags=["Automations"])


@router.get("/results", dependencies=[Depends(require_admin)])
def automation_results(current_user: User = Depends(require_admin)):
    return engine.results_for_organization(current_user.organization_id)


@router.get("/overview", dependencies=[Depends(require_admin)])
def automation_overview(current_user: User = Depends(require_admin)):
    rows = engine.results_for_organization(current_user.organization_id)
    statuses = Counter(row.get("status", "unknown") for row in rows)
    external_ai_configured = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    return {
        "engine_status": "operational",
        "safe_local_analysis": True,
        "external_ai_status": "configured" if external_ai_configured else "local_only",
        "total_executions": len(rows),
        "completed": statuses.get("completed", 0),
        "failed": statuses.get("failed", 0),
        "recent": list(reversed(rows[-20:])),
        "retention": "current_instance",
    }
