from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models import Activity, User
from app.schemas.activity import ActivityRead

router = APIRouter(prefix="/activities", tags=["Activity"])


@router.get("", response_model=list[ActivityRead])
def list_activities(entity: str | None = Query(default=None), entity_id: int | None = Query(default=None), limit: int = Query(100, ge=1, le=200), current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    statement = select(Activity).where(Activity.tenant_id == current_user.tenant_id)
    if entity:
        statement = statement.where(Activity.entity == entity)
    if entity_id is not None:
        statement = statement.where(Activity.entity_id == entity_id)
    return db.scalars(statement.order_by(Activity.created_at.desc()).limit(limit)).all()
