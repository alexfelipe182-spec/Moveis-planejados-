import json
import sys
from decimal import Decimal
from types import ModuleType, SimpleNamespace

from app.services.quote_ai import analyze_quote


def analyze_local(monkeypatch, *, base_cost: str, suggested_total: str, profit_margin: str, **context):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return analyze_quote(
        base_cost=Decimal(base_cost),
        suggested_total=Decimal(suggested_total),
        profit_margin=Decimal(profit_margin),
        **context,
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
    assert result["analysis_source"] == "local-fallback"
    assert json.loads(result["ai_analysis"])["source"] == "local-fallback"


def test_external_ai_success_replaces_only_analysis_insights(monkeypatch):
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
    assert result["analysis_source"] == "openai-assisted"
    assert json.loads(result["ai_analysis"])["summary"] == "ok"
    assert json.loads(result["ai_analysis"])["financial_values_locked"] is True
    assert result["requires_approval"] is True
    assert calls[0]["model"] == "test-model"


def test_invalid_external_ai_payload_keeps_safe_local_analysis(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text="resposta que não é JSON")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"
    assert json.loads(result["ai_analysis"])["financial_values_locked"] is True


def test_external_ai_insights_are_validated_and_merged_with_safety_rules(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "Há oportunidade de revisar ferragens.",
                "warnings": ["Confirme a disponibilidade das ferragens."],
                "recommendations": ["Registre o prazo do fornecedor."],
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1100.00"),
        profit_margin=Decimal("10"),
        description="Armário planejado",
        measurements="2,40 x 2,10 x 0,60m",
        materials="MDF branco 18 mm e ferragens",
    )

    assert result["analysis_source"] == "openai-assisted"
    assert "A margem de lucro está abaixo de 20%." in result["warnings"]
    assert "Confirme a disponibilidade das ferragens." in result["warnings"]
    assert "Registre o prazo do fornecedor." in result["recommendations"]
    stored = json.loads(result["ai_analysis"])
    assert stored["financial_values_locked"] is True
    assert stored["source"] == "openai-assisted"


def test_external_ai_cannot_publish_invented_financial_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "Preço ideal: R$ 9.999,00.",
                "warnings": [],
                "recommendations": ["Envie esse novo valor ao cliente."],
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"
    assert "9.999" not in result["summary"]


def test_external_ai_rejects_unexpected_fields(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "Análise técnica concluída.",
                "warnings": [],
                "recommendations": [],
                "suggested_total": 9999,
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"


def test_external_ai_rejects_oversized_response_before_using_it(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "A" * 25_000,
                "warnings": [],
                "recommendations": [],
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"


def test_external_ai_requires_all_contract_fields(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "Análise técnica concluída.",
                "warnings": [],
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"


def test_external_ai_rejects_non_text_list_items(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "Análise técnica concluída.",
                "warnings": [{"message": "estrutura inesperada"}],
                "recommendations": [],
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"


def test_external_ai_rejects_currency_written_in_words(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "Análise técnica concluída.",
                "warnings": [],
                "recommendations": ["Defina o valor em nove mil reais."],
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"


def test_blank_api_key_keeps_normal_local_analysis(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    fake_openai = ModuleType("openai")

    class UnexpectedOpenAI:
        def __init__(self, **kwargs):
            raise AssertionError("blank key must not initialize provider")

    fake_openai.OpenAI = UnexpectedOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-analysis"


def test_empty_external_response_is_disclosed_as_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text="")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"


def test_external_ai_rejects_invisible_direction_override(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_openai = ModuleType("openai")

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps({
                "summary": "Análise segura \u202e texto invertido",
                "warnings": [],
                "recommendations": [],
            }))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    result = analyze_quote(
        base_cost=Decimal("1000.00"),
        suggested_total=Decimal("1300.00"),
        profit_margin=Decimal("30"),
    )

    assert result["analysis_source"] == "local-fallback"


def test_context_analysis_flags_missing_measurements_and_materials(monkeypatch):
    result = analyze_local(
        monkeypatch,
        base_cost="1000.00",
        suggested_total="1300.00",
        profit_margin="30",
        description="Móvel planejado",
        measurements="",
        materials=None,
    )

    assert "As medidas do projeto ainda não foram informadas." in result["warnings"]
    assert "Os materiais do projeto ainda não foram informados." in result["warnings"]
