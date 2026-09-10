from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Project, Quote, Tenant, User
from app.schemas import QuoteRead
from app.services.automation import enqueue, process_job, record_change
from app.services.plans import ensure_capacity

router = APIRouter(prefix="/quotes", tags=["Quotes"])


class QuoteDecisionRequest(BaseModel):
    status: Literal["approved", "rejected"]


class QuoteCommercialStatusRequest(BaseModel):
    status: Literal["accepted", "declined"]


@router.patch(
    "/{item_id}/decision",
    response_model=QuoteRead,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def decide_quote(
    item_id: int,
    payload: QuoteDecisionRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = crud.get_item_for_update(db, Quote, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if item.status != "analysis":
        raise HTTPException(
            status_code=409,
            detail="Orçamento precisa estar em análise para aprovação ou rejeição",
        )

    item.status = payload.status
    db.add(
        Activity(
            user_id=current_user.id,
            action=payload.status,
            entity="quote",
            entity_id=item.id,
            description=(
                f"{'Aprovou' if payload.status == 'approved' else 'Rejeitou'} "
                f"quote #{item.id}"
            ),
        )
    )
    activity = next(obj for obj in db.new if isinstance(obj, Activity))
    record_change(db, tenant_id=current_user.tenant_id, event_type="quote." + ("shared" if item.status == "sent" else item.status),
                  entity_id=item.id, user_id=current_user.id, activity=activity)
    db.commit()
    db.refresh(item)

    return item


@router.post(
    "/{item_id}/shared",
    response_model=QuoteRead,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def record_quote_share(
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = crud.get_item_for_update(db, Quote, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if item.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Somente orçamentos aprovados podem ser enviados ao cliente",
        )

    item.status = "sent"
    db.add(
        Activity(
            user_id=current_user.id,
            action="shared",
            entity="quote",
            entity_id=item.id,
            description=f"Registrou envio da proposta do quote #{item.id} ao cliente",
        )
    )
    activity = next(obj for obj in db.new if isinstance(obj, Activity))
    record_change(db, tenant_id=current_user.tenant_id, event_type="quote." + ("shared" if item.status == "sent" else item.status),
                  entity_id=item.id, user_id=current_user.id, activity=activity)
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/{item_id}/commercial-status",
    response_model=QuoteRead,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def update_quote_commercial_status(
    item_id: int,
    payload: QuoteCommercialStatusRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = db.get(Tenant, current_user.tenant_id)
    # Lock commercial capacity before quote, consistently with quote creation.
    from sqlalchemy import select
    db.scalar(select(Tenant).where(Tenant.id == tenant.id).with_for_update())
    item = crud.get_item_for_update(db, Quote, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if item.status == payload.status:
        return item
    if item.status != "sent":
        raise HTTPException(
            status_code=409,
            detail="A proposta precisa estar enviada e aguardando o cliente",
        )

    if payload.status == "accepted" and not db.query(Project).filter(Project.quote_id == item.id).first():
        ensure_capacity(db, tenant, "projects")
    item.status = payload.status
    label = "aceitou" if payload.status == "accepted" else "recusou"

    db.add(
        Activity(
            user_id=current_user.id,
            action=payload.status,
            entity="quote",
            entity_id=item.id,
            description=f"Registrou que o cliente {label} a proposta do quote #{item.id}",
        )
    )

    if payload.status == "accepted":
        job = enqueue(db, tenant_id=current_user.tenant_id, event_type="quote.accepted",
                      payload={"entity_id": item.id, "user_id": current_user.id},
                      idempotency_key=f"quote.accepted:{item.id}")
        process_job(db, job)
    else:
        activity = next(obj for obj in db.new if isinstance(obj, Activity))
        record_change(db, tenant_id=current_user.tenant_id, event_type="quote.declined",
                      entity_id=item.id, user_id=current_user.id, activity=activity)

    db.commit()
    db.refresh(item)

    return item
