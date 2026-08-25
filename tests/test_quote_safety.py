import json

from app.services.quote_ai import analyze_quote
from app.services.quote_pricing import calculate_quote_suggestion


def test_quote_ai_has_local_safe_fallback_without_provider():
    pricing = calculate_quote_suggestion(
        material_cost=1000,
        hardware_cost=200,
        labor_cost=500,
        finishing_cost=100,
        profit_margin=30,
    )
    result = analyze_quote(
        base_cost=pricing["base_cost"],
        suggested_total=pricing["suggested_total"],
        profit_margin=pricing["profit_margin"],
    )
    assert result["ai_analysis"]
    analysis = json.loads(result["ai_analysis"])
    assert analysis["financial_values_locked"] is True
    assert result["requires_approval"] is True


def test_quote_pricing_is_deterministic_and_never_negative():
    pricing = calculate_quote_suggestion(
        material_cost=1000,
        hardware_cost=200,
        labor_cost=500,
        finishing_cost=100,
        profit_margin=30,
    )
    assert pricing["base_cost"] == 1800
    assert pricing["suggested_total"] == 2340
    assert pricing["suggested_total"] >= pricing["base_cost"]
