from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Activity, Customer, User
from app.schemas.activity import ActivityRead
from app.tenancy import tenant_get

router = APIRouter(prefix="/customers", tags=["Customers"], dependencies=[Depends(get_current_user)])


@router.get("/{customer_id}/history", response_model=list[ActivityRead])
def customer_history(customer_id: int, limit: int = Query(100, ge=1, le=200), current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not tenant_get(db, Customer, customer_id, current_user):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    stmt = select(Activity).where(Activity.tenant_id == current_user.tenant_id, Activity.entity == "customer", Activity.entity_id == customer_id).order_by(Activity.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()
