from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Quote, User
from app.schemas import QuoteRead
from app.services.automation import engine

router = APIRouter(prefix="/quotes", tags=["Quotes"])


class QuoteDecisionRequest(BaseModel):
    status: Literal["approved", "rejected"]


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
    item = crud.get_item(db, Quote, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if item.status != "analysis":
        raise HTTPException(
            status_code=409,
            detail="Orçamento precisa estar em análise para aprovação ou rejeição",
        )

    previous_status = item.status
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
    db.commit()
    db.refresh(item)

    engine.emit(
        f"quote.{payload.status}",
        {
            "entity": "quote",
            "item_id": item.id,
            "user_id": current_user.id,
            "previous_status": previous_status,
            "status": payload.status,
            "suggested_total": item.suggested_total,
        },
    )
    return item


@router.post(
    "/{item_id}/shared",
    status_code=204,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def record_quote_share(
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = crud.get_item(db, Quote, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if item.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Somente orçamentos aprovados podem ser enviados ao cliente",
        )

    db.add(
        Activity(
            user_id=current_user.id,
            action="shared",
            entity="quote",
            entity_id=item.id,
            description=f"Registrou envio da proposta do quote #{item.id} ao cliente",
        )
    )
    db.commit()
    engine.emit(
        "quote.shared",
        {
            "entity": "quote",
            "item_id": item.id,
            "user_id": current_user.id,
            "status": item.status,
            "suggested_total": item.suggested_total,
        },
    )
