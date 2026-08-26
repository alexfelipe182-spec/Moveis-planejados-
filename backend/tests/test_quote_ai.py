import json
import sys
from decimal import Decimal
from types import ModuleType, SimpleNamespace

from app.services.quote_ai import analyze_quote


def analyze_local(monkeypatch, *, base_cost: str, suggested_total: str, profit_margin: str):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return analyze_quote(
        base_cost=Decimal(base_cost),
        suggested_total=Decimal(suggested_total),
        profit_margin=Decimal(profit_margin),
    )


def test_quote_analysis_requires_approval_and_does_not_change_price(monkeypatch):
    result = analyze_local(
        monkeypatch,
        base_cost="2500.00",
        suggested_total="3250.00",
        profit_margin="30",
    )

    assert result["base_cost"] == Decimal("2500.00")
    assert result["suggested_total"] == Decimal("3250.00")
    assert result["profit_margin"] == Decimal("30")
    assert result["requires_approval"] is True
    assert result["warnings"] == []

    local = json.loads(result["ai_analysis"])
    assert local["source"] == "local-analysis"
    assert local["financial_values_locked"] is True


def test_quote_analysis_warns_about_low_margin(monkeypatch):
    result = analyze_local(
        monkeypatch,
        base_cost="1000.00",
        suggested_total="1100.00",
        profit_margin="10",
    )

    assert "A margem de lucro está abaixo de 20%." in result["warnings"]
    assert "Revise a margem antes da aprovação." in result["recommendations"]
    assert result["requires_approval"] is True


def test_quote_analysis_warns_when_costs_are_missing(monkeypatch):
    result = analyze_local(
        monkeypatch,
        base_cost="0",
        suggested_total="1500.00",
        profit_margin="30",
    )

    assert "O orçamento ainda não possui custos cadastrados." in result["warnings"]
    assert "Cadastre os custos antes de enviar ao cliente." in result["recommendations"]

    local = json.loads(result["ai_analysis"])
    assert "O orçamento ainda não possui custos cadastrados." in local["warnings"]


def test_quote_analysis_warns_when_price_does_not_exceed_cost(monkeypatch):
    result = analyze_local(
        monkeypatch,
        base_cost="2000.00",
        suggested_total="2000.00",
        profit_margin="25",
    )

    assert "O preço sugerido não supera o custo-base." in result["warnings"]
    assert "Revise a margem e os custos antes da aprovação." in result["recommendations"]


def test_quote_analysis_flags_very_high_margin_for_review(monkeypatch):
    result = analyze_local(
        monkeypatch,
        base_cost="1000.00",
        suggested_total="1800.00",
        profit_margin="55",
    )

    assert result["warnings"] == []
    assert "Confirme se a margem elevada está adequada ao mercado." in result["recommendations"]


def test_external_ai_failure_falls_back_without_breaking_quote(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    fake_openai = ModuleType("openai")

    class BrokenOpenAI:
        def __init__(self, **kwargs):
            raise RuntimeError("provider unavailable")

    fake_openai.OpenAI = BrokenOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["suggested_total"] == Decimal("1300.00")
    assert result["requires_approval"] is True
    assert json.loads(result["ai_analysis"])["source"] == "local-analysis"


def test_external_ai_success_replaces_only_analysis_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    fake_openai = ModuleType("openai")
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                output_text='{"summary":"ok","warnings":[],"recommendations":[]}'
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1350.00"),
        profit_margin=Decimal("35"),
    )

    assert result["base_cost"] == Decimal("1000.00")
    assert result["suggested_total"] == Decimal("1350.00")
    assert result["profit_margin"] == Decimal("35")
    assert result["ai_analysis"] == '{"summary":"ok","warnings":[],"recommendations":[]}'
    assert result["requires_approval"] is True
    assert calls[0]["model"] == "test-model"
