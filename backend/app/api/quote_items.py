from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_cookie_csrf, require_workspace_admin
from app.database import get_db
from app.models import Activity, Quote, QuoteItem, User
from app.schemas.quote_item import QuoteItemCreate, QuoteItemRead, QuoteItemUpdate

router = APIRouter(
    prefix="/quotes/{quote_id}/items",
    tags=["Quote Items"],
    dependencies=[Depends(require_admin)],
)


def _subtotal(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(Decimal("0.01"))


def _get_quote(db: Session, quote_id: int, organization_id: int) -> Quote:
    quote = db.query(Quote).filter(Quote.id == quote_id, Quote.organization_id == organization_id).one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return quote


def _get_editable_quote(db: Session, quote_id: int, organization_id: int) -> Quote:
    # Serialize item writes with decisions and refresh any cached ORM state.
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.organization_id == organization_id,
    ).with_for_update().populate_existing().one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if quote.status not in {"pending", "analysis"}:
        raise HTTPException(
            status_code=409,
            detail="Orçamento com decisão registrada não permite alterar itens; crie uma nova revisão",
        )
    return quote


def _recalculate_quote_total(db: Session, quote_id: int, organization_id: int) -> Decimal:
    items = db.query(QuoteItem).filter(
        QuoteItem.quote_id == quote_id,
        QuoteItem.organization_id == organization_id,
    ).all()
    total = sum(
        (
            Decimal(item.subtotal)
            if item.subtotal is not None
            else Decimal("0")
            for item in items
        ),
        Decimal("0"),
    ).quantize(Decimal("0.01"))
    quote = _get_quote(db, quote_id, organization_id)
    quote.total = total
    quote.suggested_total = total
    return total


@router.get("", response_model=list[QuoteItemRead])
def list_items(quote_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    organization_id = current_user.organization_id
    _get_quote(db, quote_id, organization_id)
    return db.query(QuoteItem).filter(
        QuoteItem.quote_id == quote_id,
        QuoteItem.organization_id == organization_id,
    ).order_by(QuoteItem.id).all()


@router.post(
    "",
    response_model=QuoteItemRead,
    status_code=201,
    dependencies=[Depends(require_workspace_admin), Depends(require_cookie_csrf)],
)
def create_item(
    quote_id: int,
    payload: QuoteItemCreate,
    current_user: User = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
):
    organization_id = current_user.organization_id
    _get_editable_quote(db, quote_id, organization_id)
    data = payload.model_dump()
    data.update(
        quote_id=quote_id,
        organization_id=organization_id,
        subtotal=_subtotal(payload.quantity, payload.unit_price),
    )
    item = QuoteItem(**data)
    db.add(item)
    db.flush()
    total = _recalculate_quote_total(db, quote_id, organization_id)
    db.add(
        Activity(
            organization_id=organization_id,
            user_id=current_user.id,
            action="created",
            entity="quote_item",
            entity_id=item.id,
            description=(
                f"Adicionou item #{item.id} ao orçamento #{quote_id}; "
                f"total atualizado para R$ {total}"
            ),
        )
    )
    db.commit()
    db.refresh(item)
    return item


@router.put(
    "/{item_id}",
    response_model=QuoteItemRead,
    dependencies=[Depends(require_workspace_admin), Depends(require_cookie_csrf)],
)
def update_item(
    quote_id: int,
    item_id: int,
    payload: QuoteItemUpdate,
    current_user: User = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
):
    organization_id = current_user.organization_id
    _get_editable_quote(db, quote_id, organization_id)
    item = (
        db.query(QuoteItem)
        .filter(QuoteItem.id == item_id, QuoteItem.quote_id == quote_id, QuoteItem.organization_id == organization_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do orçamento não encontrado")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    item.subtotal = _subtotal(item.quantity, item.unit_price)
    total = _recalculate_quote_total(db, quote_id, organization_id)
    db.add(
        Activity(
            organization_id=organization_id,
            user_id=current_user.id,
            action="updated",
            entity="quote_item",
            entity_id=item.id,
            description=(
                f"Atualizou item #{item.id} do orçamento #{quote_id}; "
                f"total atualizado para R$ {total}"
            ),
        )
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/{item_id}",
    status_code=204,
    dependencies=[Depends(require_workspace_admin), Depends(require_cookie_csrf)],
)
def delete_item(
    quote_id: int,
    item_id: int,
    current_user: User = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
):
    organization_id = current_user.organization_id
    _get_editable_quote(db, quote_id, organization_id)
    item = (
        db.query(QuoteItem)
        .filter(QuoteItem.id == item_id, QuoteItem.quote_id == quote_id, QuoteItem.organization_id == organization_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do orçamento não encontrado")
    db.delete(item)
    db.flush()
    total = _recalculate_quote_total(db, quote_id, organization_id)
    db.add(
        Activity(
            organization_id=organization_id,
            user_id=current_user.id,
            action="deleted",
            entity="quote_item",
            entity_id=item_id,
            description=(
                f"Removeu item #{item_id} do orçamento #{quote_id}; "
                f"total atualizado para R$ {total}"
            ),
        )
    )
    db.commit()
