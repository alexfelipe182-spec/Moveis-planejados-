from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Activity, Customer, User
from app.schemas.activity import ActivityRead

router = APIRouter(prefix="/customers", tags=["Customers"], dependencies=[Depends(get_current_user)])


@router.get("/{customer_id}/history", response_model=list[ActivityRead])
def customer_history(
    customer_id: int,
    response: Response,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Annotated[str | None, Query(max_length=200)] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    organization_id = current_user.organization_id
    if not crud.get_item(db, Customer, customer_id, organization_id=organization_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    filters = [Activity.entity == "customer", Activity.entity_id == customer_id]
    total = crud.count_items(db, Activity, q=q, filters=filters, organization_id=organization_id)
    crud.pagination_headers(response, total=total, offset=offset, limit=limit)
    return crud.list_items(db, Activity, offset=offset, limit=limit, q=q, filters=filters, organization_id=organization_id)
