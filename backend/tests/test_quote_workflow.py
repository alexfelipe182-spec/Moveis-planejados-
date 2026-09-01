from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.quote_workflow import ensure_quote_editable


@pytest.mark.parametrize("status", ["approved", "sent", "accepted", "declined", "rejected", "completed"])
def test_decided_quote_rejects_technical_mutation(status):
    """Defect: approved or customer-visible proposals could be silently rewritten."""
    with pytest.raises(HTTPException) as exc_info:
        ensure_quote_editable(SimpleNamespace(status=status))

    assert exc_info.value.status_code == 409
    assert "nova revisão" in exc_info.value.detail


@pytest.mark.parametrize("status", ["pending", "analysis"])
def test_undecided_quote_allows_technical_mutation(status):
    quote = SimpleNamespace(status=status)

    assert ensure_quote_editable(quote) is quote
