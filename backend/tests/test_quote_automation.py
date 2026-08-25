from decimal import Decimal

from app.services.automation import engine


def test_quote_created_triggers_analysis():
    before = len(engine.results)

    event = engine.emit(
        "quote.created",
        {
            "quote_id": 1,
            "base_cost": Decimal("2500.00"),
            "suggested_total": Decimal("3250.00"),
            "profit_margin": Decimal("30"),
        },
    )

    assert event.name == "quote.created"
    assert len(engine.results) == before + 1
    assert engine.results[-1]["action"] == "analyze_quote"
    assert engine.results[-1]["result"]["requires_approval"] is True
