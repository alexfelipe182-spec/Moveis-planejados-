import sys
from decimal import Decimal
from types import ModuleType, SimpleNamespace

from app.services.quote_brief import (
    CatalogMaterial,
    QuoteBrief,
    QuoteBriefItem,
    QuoteRequirement,
    build_quote_preview,
    extract_quote_brief,
    extract_quote_brief_result,
)


def armario_brief() -> QuoteBrief:
    return QuoteBrief(
        normalized_description="Armário de 3 metros em MDF branco, com seis portas e três gavetas.",
        measurements_summary="3,00 m de largura",
        materials_summary="MDF branco",
        items=[
            QuoteBriefItem(
                name="Armário",
                quantity=1,
                width_m=3,
                doors=6,
                drawers=3,
            )
        ],
        requirements=[
            QuoteRequirement(name="MDF branco", kind="mdf", quantity=3, unit="chapa"),
            QuoteRequirement(name="Dobradiça", kind="hardware", quantity=12, unit="un"),
            QuoteRequirement(name="Corrediça", kind="hardware", quantity=3, unit="par"),
            QuoteRequirement(name="Montagem", kind="service", quantity=8, unit="h"),
            QuoteRequirement(name="Laca branca", kind="finish", quantity=1, unit="serviço"),
        ],
        finish="Laca branca",
        questions=["Confirmar altura e profundidade."],
        confidence_score=82,
    )


def _fake_openai(monkeypatch, *, broken: bool = False):
    calls = []
    fake_openai = ModuleType("openai")

    if broken:
        class BrokenOpenAI:
            def __init__(self, **kwargs):
                raise RuntimeError("provider unavailable")

        fake_openai.OpenAI = BrokenOpenAI
    else:
        class FakeCompletions:
            def parse(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(parsed=armario_brief(), refusal=None)
                        )
                    ]
                )

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        fake_openai.OpenAI = FakeOpenAI

    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    return calls


def test_extract_quote_brief_uses_a_validated_structured_output(monkeypatch):
    """Defect: free-form model text could omit doors, drawers or measurements."""
    monkeypatch.setenv("OPENAI_API_DISABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    calls = _fake_openai(monkeypatch)

    interpretation = extract_quote_brief_result(
        "Quero um armário de 3 metros, MDF branco, seis portas e três gavetas."
    )
    result = interpretation.brief

    assert interpretation.source == "openai"
    assert result.items[0].width_m == 3
    assert result.items[0].doors == 6
    assert result.items[0].drawers == 3
    assert calls[0]["model"] == "test-model"
    assert calls[0]["response_format"] is QuoteBrief


def test_extract_quote_brief_compatibility_returns_only_brief(monkeypatch):
    monkeypatch.setenv("OPENAI_API_DISABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    _fake_openai(monkeypatch)

    result = extract_quote_brief("Armário em MDF branco")

    assert isinstance(result, QuoteBrief)
    assert result.normalized_description.startswith("Armário")


def test_extract_quote_brief_falls_back_safely_without_a_provider_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_DISABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    interpretation = extract_quote_brief_result("Armário em MDF branco com 3,00m x 2,40m")
    result = interpretation.brief

    assert interpretation.source == "assisted_local"
    assert result.normalized_description.startswith("Armário em MDF branco")
    assert result.measurements_summary == "3,00m x 2,40m"
    assert "MDF" in (result.materials_summary or "")
    assert result.requirements == []
    assert any("assistida local" in question for question in result.questions)


def test_extract_quote_brief_falls_back_when_provider_is_unavailable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_DISABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    _fake_openai(monkeypatch, broken=True)

    interpretation = extract_quote_brief_result("Armário em MDF branco")
    result = interpretation.brief

    assert interpretation.source == "assisted_local"
    assert result.normalized_description == "Armário em MDF branco"
    assert result.requirements == []
    assert any("assistida local" in question for question in result.questions)


def test_catalog_prices_are_deterministic_and_unmatched_items_stay_unpriced():
    """Defect: the model could invent a price for an absent catalog item."""
    catalog = [
        CatalogMaterial(id=1, name="MDF branco", kind="mdf", unit="chapa", unit_cost=Decimal("180"), waste_percent=Decimal("10")),
        CatalogMaterial(id=2, name="Dobradiça", kind="hardware", unit="un", unit_cost=Decimal("15"), waste_percent=Decimal("0")),
        CatalogMaterial(id=3, name="Corrediça", kind="hardware", unit="par", unit_cost=Decimal("25"), waste_percent=Decimal("0")),
        CatalogMaterial(id=4, name="Montagem", kind="service", unit="h", unit_cost=Decimal("40"), waste_percent=Decimal("0")),
    ]

    preview = build_quote_preview(
        armario_brief(),
        catalog,
        profit_margin=Decimal("30"),
        interpretation_source="openai",
    )

    assert preview.interpretation_source == "openai"
    assert preview.material_cost == Decimal("594.00")
    assert preview.hardware_cost == Decimal("255.00")
    assert preview.labor_cost == Decimal("320.00")
    assert preview.finishing_cost == Decimal("0.00")
    assert preview.base_cost == Decimal("1169.00")
    assert preview.suggested_total == Decimal("1519.70")
    assert [item.requirement.name for item in preview.unpriced_items] == ["Laca branca"]
    assert preview.requires_approval is True


def test_assisted_preview_preserves_source_without_inventing_price():
    preview = build_quote_preview(
        QuoteBrief(
            normalized_description="Armário em MDF branco",
            items=[QuoteBriefItem(name="Móvel planejado")],
            requirements=[],
            questions=["Confirmar custos."],
            confidence_score=25,
        ),
        [],
        profit_margin=Decimal("30"),
        interpretation_source="assisted_local",
    )

    assert preview.interpretation_source == "assisted_local"
    assert preview.base_cost == Decimal("0.00")
    assert preview.suggested_total == Decimal("0.00")
    assert preview.priced_items == []


def test_catalog_match_requires_compatible_kind_and_unit():
    brief = armario_brief().model_copy(
        update={
            "requirements": [
                QuoteRequirement(name="MDF branco", kind="mdf", quantity=3, unit="m²")
            ]
        }
    )
    catalog = [
        CatalogMaterial(id=1, name="MDF branco", kind="mdf", unit="chapa", unit_cost=Decimal("180"), waste_percent=Decimal("10"))
    ]

    preview = build_quote_preview(brief, catalog, profit_margin=Decimal("30"))

    assert preview.base_cost == Decimal("0.00")
    assert preview.unpriced_items[0].reason == "Unidade incompatível com o catálogo"
