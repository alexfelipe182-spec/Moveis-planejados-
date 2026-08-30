from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Project, Quote, User
from app.schemas import QuoteRead
from app.services.automation import engine
from app.tenancy import tenant_get, tenant_query

router = APIRouter(prefix="/quotes", tags=["Quotes"])


class QuoteDecisionRequest(BaseModel):
    status: Literal["approved", "rejected"]


class QuoteCommercialStatusRequest(BaseModel):
    status: Literal["accepted", "declined"]


def _quote(db: Session, item_id: int, user: User) -> Quote:
    item = tenant_get(db, Quote, item_id, user)
    if not item:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return item


def _activity(user: User, action: str, entity: str, entity_id: int, description: str) -> Activity:
    return Activity(tenant_id=user.tenant_id, user_id=user.id, action=action, entity=entity, entity_id=entity_id, description=description)


@router.patch("/{item_id}/decision", response_model=QuoteRead, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def decide_quote(item_id: int, payload: QuoteDecisionRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = _quote(db, item_id, current_user)
    if item.status != "analysis":
        raise HTTPException(status_code=409, detail="Orçamento precisa estar em análise para aprovação ou rejeição")
    previous_status = item.status
    item.status = payload.status
    db.add(_activity(current_user, payload.status, "quote", item.id, f"{'Aprovou' if payload.status == 'approved' else 'Rejeitou'} quote #{item.id}"))
    db.commit(); db.refresh(item)
    engine.emit(f"quote.{payload.status}", {"tenant_id": current_user.tenant_id, "entity": "quote", "item_id": item.id, "user_id": current_user.id, "previous_status": previous_status, "status": payload.status, "suggested_total": item.suggested_total})
    return item


@router.post("/{item_id}/shared", response_model=QuoteRead, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def record_quote_share(item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = _quote(db, item_id, current_user)
    if item.status != "approved":
        raise HTTPException(status_code=409, detail="Somente orçamentos aprovados podem ser enviados ao cliente")
    previous_status = item.status
    item.status = "sent"
    db.add(_activity(current_user, "shared", "quote", item.id, f"Registrou envio da proposta do quote #{item.id} ao cliente"))
    db.commit(); db.refresh(item)
    engine.emit("quote.shared", {"tenant_id": current_user.tenant_id, "entity": "quote", "item_id": item.id, "user_id": current_user.id, "previous_status": previous_status, "status": item.status, "suggested_total": item.suggested_total})
    return item


@router.patch("/{item_id}/commercial-status", response_model=QuoteRead, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def update_quote_commercial_status(item_id: int, payload: QuoteCommercialStatusRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = _quote(db, item_id, current_user)
    if item.status != "sent":
        raise HTTPException(status_code=409, detail="A proposta precisa estar enviada e aguardando o cliente")
    previous_status = item.status
    item.status = payload.status
    label = "aceitou" if payload.status == "accepted" else "recusou"
    created_project: Project | None = None
    db.add(_activity(current_user, payload.status, "quote", item.id, f"Registrou que o cliente {label} a proposta do quote #{item.id}"))
    if payload.status == "accepted":
        existing_project = tenant_query(db, Project, current_user).filter(Project.quote_id == item.id).one_or_none()
        if existing_project:
            raise HTTPException(status_code=409, detail="Este orçamento já possui um projeto vinculado")
        created_project = Project(tenant_id=current_user.tenant_id, customer_id=item.customer_id, quote_id=item.id, name=f"Projeto do orçamento #{item.id}", description=item.description, measurements=item.measurements, materials=item.materials, status="planning")
        db.add(created_project); db.flush()
        db.add(_activity(current_user, "created_from_quote", "project", created_project.id, f"Criou automaticamente o projeto #{created_project.id} a partir do quote #{item.id} aceito pelo cliente"))
    db.commit(); db.refresh(item)
    engine.emit(f"quote.{payload.status}", {"tenant_id": current_user.tenant_id, "entity": "quote", "item_id": item.id, "user_id": current_user.id, "previous_status": previous_status, "status": item.status, "suggested_total": item.suggested_total, "project_id": created_project.id if created_project else None})
    if created_project:
        engine.emit("project.created", {"tenant_id": current_user.tenant_id, "entity": "project", "item_id": created_project.id, "user_id": current_user.id, "quote_id": item.id, "customer_id": item.customer_id, "status": created_project.status})
    return item
