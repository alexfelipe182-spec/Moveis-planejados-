from decimal import Decimal

import pytest

from app.services.quote_pricing import calculate_quote_suggestion


def test_quote_pricing_calculates_cost_and_margin():
    result = calculate_quote_suggestion(
        material_cost=Decimal("800"),
        hardware_cost=Decimal("350"),
        labor_cost=Decimal("900"),
        finishing_cost=Decimal("450"),
        profit_margin=Decimal("30"),
    )

    assert result["base_cost"] == Decimal("2500.00")
    assert result["suggested_total"] == Decimal("3250.00")


def test_quote_pricing_rejects_invalid_margin():
    with pytest.raises(ValueError):
        calculate_quote_suggestion(profit_margin=Decimal("101"))
