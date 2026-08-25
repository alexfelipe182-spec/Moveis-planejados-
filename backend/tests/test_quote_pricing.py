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


def test_pricing_is_deterministic_and_quantized():
    result = calculate_quote_suggestion(
        material_cost=Decimal("1000.005"),
        hardware_cost=Decimal("200"),
        labor_cost=Decimal("500"),
        finishing_cost=Decimal("100"),
        profit_margin=Decimal("30"),
    )
    assert result["base_cost"] == Decimal("1800.01")
    assert result["suggested_total"] == Decimal("2340.01")
    assert all(value.as_tuple().exponent == -2 for value in result.values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("material_cost", Decimal("-0.01")),
        ("hardware_cost", Decimal("-0.01")),
        ("labor_cost", Decimal("-0.01")),
        ("finishing_cost", Decimal("-0.01")),
    ],
)
def test_negative_costs_are_rejected(field, value):
    with pytest.raises(ValueError, match="não podem ser negativos"):
        calculate_quote_suggestion(**{field: value})


def test_quote_pricing_rejects_invalid_margin():
    with pytest.raises(ValueError, match="entre 0 e 100"):
        calculate_quote_suggestion(profit_margin=Decimal("101"))


def test_zero_cost_keeps_zero_total():
    result = calculate_quote_suggestion(profit_margin=Decimal("100"))
    assert result["base_cost"] == Decimal("0.00")
    assert result["suggested_total"] == Decimal("0.00")
