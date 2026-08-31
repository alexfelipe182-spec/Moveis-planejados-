from decimal import Decimal

from app.services.quote_intelligence import recommend_from_history


def test_recommendation_raises_markup_when_history_shows_cost_overrun():
    result = recommend_from_history(
        base_cost=Decimal("10000.00"),
        requested_margin=Decimal("20.00"),
        historical_markups=[Decimal("18.00"), Decimal("20.00"), Decimal("22.00")],
        historical_cost_variances=[Decimal("10.00"), Decimal("12.00"), Decimal("8.00")],
    )
    assert result["sample_size"] == 3
    assert result["average_real_markup_percent"] == Decimal("20.00")
    assert result["average_cost_variance_percent"] == Decimal("10.00")
    assert result["recommended_margin_percent"] == Decimal("30.00")
    assert result["recommended_total"] == Decimal("13000.00")
    assert result["risk_level"] == "medium"
    assert result["confidence"] == "medium"


def test_recommendation_without_history_uses_conservative_floor():
    result = recommend_from_history(
        base_cost=Decimal("8000.00"),
        requested_margin=Decimal("15.00"),
        historical_markups=[],
        historical_cost_variances=[],
    )
    assert result["sample_size"] == 0
    assert result["recommended_margin_percent"] == Decimal("25.00")
    assert result["recommended_total"] == Decimal("10000.00")
    assert result["risk_level"] == "medium"
    assert result["confidence"] == "low"
