from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Activity, User
from app.schemas.activity import ActivityRead

router = APIRouter(prefix="/activities", tags=["Activities"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ActivityRead])
def list_activities(
    entity: str | None = None,
    entity_id: int | None = Query(default=None, gt=0),
    limit: int = Query(100, ge=1, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Activity).order_by(Activity.created_at.desc()).limit(limit)
    if entity:
        stmt = stmt.where(Activity.entity == entity)
    if entity_id:
        stmt = stmt.where(Activity.entity_id == entity_id)
    return db.scalars(stmt).all()
