from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes import update_quote
from app.models import Quote
from app.schemas import QuoteUpdate


def test_edit_locks_and_refreshes_quote_before_checking_decision():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(status="approved")
    with pytest.raises(HTTPException) as error:
        update_quote(123, QuoteUpdate(description="Novo escopo"), current_user=SimpleNamespace(id=1), db=db)
    assert error.value.status_code == 409
    db.get.assert_called_once_with(Quote, 123, with_for_update=True, populate_existing=True)
    db.commit.assert_not_called()


def test_edit_of_missing_quote_returns_404_after_locked_lookup():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as error:
        update_quote(123, QuoteUpdate(description="Novo escopo"), current_user=SimpleNamespace(id=1), db=db)
    assert error.value.status_code == 404
