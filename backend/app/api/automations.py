from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models import AutomationJob, User

router = APIRouter(prefix="/automations", tags=["Automations"])


@router.get("")
def list_automations(current_user: User = Depends(require_admin), db: Session = Depends(get_db),
                     limit: int = Query(30, ge=1, le=100)):
    scope = AutomationJob.tenant_id == current_user.tenant_id
    counts = dict(db.execute(select(AutomationJob.status, func.count()).where(scope).group_by(AutomationJob.status)).all())
    rows = db.scalars(select(AutomationJob).where(scope).order_by(AutomationJob.id.desc()).limit(limit)).all()
    return {
        "counts": {status: counts.get(status, 0) for status in ("pending", "retry", "completed", "failed")},
        "last_execution": db.scalar(select(func.max(AutomationJob.processed_at)).where(scope)),
        # No payloads, provider identifiers, request contents or raw errors.
        "jobs": [{"id": row.id, "event_type": row.event_type, "status": row.status,
                  "attempts": row.attempts, "created_at": row.created_at,
                  "available_at": row.available_at, "processed_at": row.processed_at,
                  "error_code": row.last_error} for row in rows],
    }
