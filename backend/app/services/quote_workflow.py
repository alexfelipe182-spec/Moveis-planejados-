from typing import TypeVar

from fastapi import HTTPException

QuoteLike = TypeVar("QuoteLike")
EDITABLE_QUOTE_STATUSES = frozenset({"pending", "analysis"})


def ensure_quote_editable(quote: QuoteLike) -> QuoteLike:
    if getattr(quote, "status", None) not in EDITABLE_QUOTE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "Orçamento com decisão registrada não pode ser alterado; "
                "crie uma nova revisão"
            ),
        )
    return quote
