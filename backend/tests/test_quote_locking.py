from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api import quote_decisions, quote_items
from app.models import Quote
from app.schemas.quote_item import QuoteItemCreate, QuoteItemUpdate


def test_editable_quote_locks_and_refreshes_the_parent_row():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=7, status="analysis")
    assert quote_items._get_editable_quote(db, 7) is db.get.return_value
    db.get.assert_called_once_with(Quote, 7, with_for_update=True, populate_existing=True)


@pytest.mark.parametrize("existing", [None, SimpleNamespace(id=7, status="approved")])
def test_locked_quote_preserves_missing_and_noneditable_responses(existing):
    db = MagicMock()
    db.get.return_value = existing
    with pytest.raises(HTTPException) as error:
        quote_items._get_editable_quote(db, 7)
    assert error.value.status_code == (404 if existing is None else 409)
    db.get.assert_called_once_with(Quote, 7, with_for_update=True, populate_existing=True)


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_every_item_mutation_takes_parent_lock_before_changing_data(operation):
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=7, status="approved")
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as error:
        if operation == "create":
            quote_items.create_item(7, QuoteItemCreate(name="Item", unit_price="1"), user, db)
        elif operation == "update":
            quote_items.update_item(7, 8, QuoteItemUpdate(quantity="2"), user, db)
        else:
            quote_items.delete_item(7, 8, user, db)
    assert error.value.status_code == 409
    db.get.assert_called_once_with(Quote, 7, with_for_update=True, populate_existing=True)
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()
    db.commit.assert_not_called()


def invoke_transition(operation, db):
    user = SimpleNamespace(id=1)
    if operation == "decision":
        return quote_decisions.decide_quote(
            7, quote_decisions.QuoteDecisionRequest(status="approved"), user, db
        )
    if operation == "share":
        return quote_decisions.record_quote_share(7, user, db)
    return quote_decisions.update_quote_commercial_status(
        7, quote_decisions.QuoteCommercialStatusRequest(status="accepted"), user, db
    )


@pytest.mark.parametrize(
    ("operation", "initial", "expected"),
    [("decision", "analysis", "approved"), ("share", "approved", "sent"), ("commercial", "sent", "accepted")],
)
def test_transitions_take_the_same_row_lock_before_checking_status(monkeypatch, operation, initial, expected):
    db = MagicMock()
    item = SimpleNamespace(id=7, status=initial, suggested_total=Decimal("100"))
    db.get.return_value = item
    monkeypatch.setattr(quote_decisions.engine, "emit", MagicMock())
    assert invoke_transition(operation, db) is item
    db.get.assert_called_once_with(Quote, 7, with_for_update=True, populate_existing=True)
    assert item.status == expected
    db.commit.assert_called_once()


@pytest.mark.parametrize("operation", ["decision", "share", "commercial"])
@pytest.mark.parametrize("existing", [None, SimpleNamespace(id=7, status="accepted")])
def test_transitions_reject_missing_or_advanced_state_without_writes(operation, existing):
    db = MagicMock()
    db.get.return_value = existing
    with pytest.raises(HTTPException) as error:
        invoke_transition(operation, db)
    assert error.value.status_code == (404 if existing is None else 409)
    db.get.assert_called_once_with(Quote, 7, with_for_update=True, populate_existing=True)
    db.add.assert_not_called()
    db.commit.assert_not_called()
