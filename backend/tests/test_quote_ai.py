from decimal import Decimal

from app.services.quote_ai import analyze_quote


def test_quote_analysis_requires_approval_and_does_not_change_price():
    result = analyze_quote(
        base_cost=Decimal("2500.00"),
        suggested_total=Decimal("3250.00"),
        profit_margin=Decimal("30"),
    )

    assert result["suggested_total"] == Decimal("3250.00")
    assert result["requires_approval"] is True


def test_quote_analysis_warns_about_low_margin():
    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1100.00"),
        profit_margin=Decimal("10"),
    )

    assert result["warnings"]
    assert result["requires_approval"] is True
