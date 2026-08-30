from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.database import get_db
from app.models import Activity, Quote, QuoteItem, User
from app.schemas.quote_item import QuoteItemCreate, QuoteItemRead, QuoteItemUpdate
from app.tenancy import tenant_get, tenant_query

router = APIRouter(prefix="/quotes/{quote_id}/items", tags=["Quote Items"], dependencies=[Depends(get_current_user)])


def _subtotal(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(Decimal("0.01"))


def _get_quote(db: Session, quote_id: int, current_user: User) -> Quote:
    quote = tenant_get(db, Quote, quote_id, current_user)
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return quote


def _recalculate_quote_total(db: Session, quote_id: int, current_user: User) -> Decimal:
    items = tenant_query(db, QuoteItem, current_user).filter(QuoteItem.quote_id == quote_id).all()
    total = sum((Decimal(item.subtotal) if item.subtotal is not None else Decimal("0") for item in items), Decimal("0")).quantize(Decimal("0.01"))
    quote = _get_quote(db, quote_id, current_user)
    quote.total = total
    quote.suggested_total = total
    return total


@router.get("", response_model=list[QuoteItemRead])
def list_items(quote_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_quote(db, quote_id, current_user)
    return tenant_query(db, QuoteItem, current_user).filter(QuoteItem.quote_id == quote_id).order_by(QuoteItem.id).all()


@router.post("", response_model=QuoteItemRead, status_code=201, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def create_item(quote_id: int, payload: QuoteItemCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    _get_quote(db, quote_id, current_user)
    data = payload.model_dump()
    data.update(tenant_id=current_user.tenant_id, quote_id=quote_id, subtotal=_subtotal(payload.quantity, payload.unit_price))
    item = QuoteItem(**data)
    db.add(item)
    db.flush()
    total = _recalculate_quote_total(db, quote_id, current_user)
    db.add(Activity(tenant_id=current_user.tenant_id, user_id=current_user.id, action="created", entity="quote_item", entity_id=item.id, description=f"Adicionou item #{item.id} ao orçamento #{quote_id}; total atualizado para R$ {total}"))
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=QuoteItemRead, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def update_item(quote_id: int, item_id: int, payload: QuoteItemUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    _get_quote(db, quote_id, current_user)
    item = tenant_query(db, QuoteItem, current_user).filter(QuoteItem.id == item_id, QuoteItem.quote_id == quote_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item do orçamento não encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.subtotal = _subtotal(item.quantity, item.unit_price)
    total = _recalculate_quote_total(db, quote_id, current_user)
    db.add(Activity(tenant_id=current_user.tenant_id, user_id=current_user.id, action="updated", entity="quote_item", entity_id=item.id, description=f"Atualizou item #{item.id} do orçamento #{quote_id}; total atualizado para R$ {total}"))
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204, dependencies=[Depends(require_admin), Depends(require_cookie_csrf)])
def delete_item(quote_id: int, item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    _get_quote(db, quote_id, current_user)
    item = tenant_query(db, QuoteItem, current_user).filter(QuoteItem.id == item_id, QuoteItem.quote_id == quote_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item do orçamento não encontrado")
    db.delete(item)
    db.flush()
    total = _recalculate_quote_total(db, quote_id, current_user)
    db.add(Activity(tenant_id=current_user.tenant_id, user_id=current_user.id, action="deleted", entity="quote_item", entity_id=item_id, description=f"Removeu item #{item_id} do orçamento #{quote_id}; total atualizado para R$ {total}"))
    db.commit()
