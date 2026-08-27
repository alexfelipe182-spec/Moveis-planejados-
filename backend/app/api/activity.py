from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Activity, User
from app.schemas.activity import ActivityRead

router = APIRouter(prefix="/activities", tags=["Activities"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ActivityRead])
def list_activities(
    response: Response,
    entity: str | None = None,
    entity_id: int | None = Query(default=None, gt=0),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Annotated[str | None, Query(max_length=200)] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filters = []
    if entity:
        filters.append(Activity.entity == entity)
    if entity_id:
        filters.append(Activity.entity_id == entity_id)
    total = crud.count_items(db, Activity, q=q, filters=filters)
    crud.pagination_headers(response, total=total, offset=offset, limit=limit)
    return crud.list_items(db, Activity, offset=offset, limit=limit, q=q, filters=filters)
