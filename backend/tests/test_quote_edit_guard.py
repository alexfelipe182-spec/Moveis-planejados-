from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes import update_quote
from app.models import Quote
from app.schemas import QuoteUpdate


def locked_quote(db, value):
    db.query.return_value.filter.return_value.with_for_update.return_value.populate_existing.return_value.one_or_none.return_value = value


def test_edit_locks_and_refreshes_quote_before_checking_decision():
    db = MagicMock()
    locked_quote(db, SimpleNamespace(organization_id=7, status="approved"))
    with pytest.raises(HTTPException) as error:
        update_quote(123, QuoteUpdate(description="Novo escopo"), current_user=SimpleNamespace(id=1, organization_id=7), db=db)
    assert error.value.status_code == 409
    db.query.assert_called_once_with(Quote)
    db.commit.assert_not_called()


def test_edit_of_missing_quote_returns_404_after_locked_lookup():
    db = MagicMock()
    locked_quote(db, None)
    with pytest.raises(HTTPException) as error:
        update_quote(123, QuoteUpdate(description="Novo escopo"), current_user=SimpleNamespace(id=1, organization_id=7), db=db)
    assert error.value.status_code == 404
