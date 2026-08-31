from decimal import Decimal

from app.services import quote_ai
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


def test_quote_created_reuses_analysis_already_calculated_by_route(monkeypatch):
    precalculated = {
        "analysis_source": "local-analysis",
        "requires_approval": True,
        "warnings": ["Revise os dados."],
    }

    def unexpected_second_analysis(**kwargs):
        raise AssertionError("a análise não deve chamar o provedor duas vezes")

    monkeypatch.setattr(quote_ai, "analyze_quote", unexpected_second_analysis)
    before = len(engine.results)

    engine.emit("quote.created", {"quote_id": 1, "analysis": precalculated})

    assert len(engine.results) == before + 1
    assert engine.results[-1]["status"] == "completed"
    assert engine.results[-1]["action"] == "analyze_quote"
    assert engine.results[-1]["result"] == precalculated


def test_quote_analysis_action_keeps_same_name_when_it_fails(monkeypatch):
    def fail_analysis(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(quote_ai, "analyze_quote", fail_analysis)

    engine.emit("quote.created", {
        "base_cost": Decimal("1000.00"),
        "suggested_total": Decimal("1300.00"),
        "profit_margin": Decimal("30"),
    })

    assert engine.results[-1]["status"] == "failed"
    assert engine.results[-1]["action"] == "analyze_quote"
