import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from sqlalchemy.orm import Session

from app.services.openai_config import structured_completion
from app.services.quote_pricing import calculate_quote_suggestion


MaterialKind = Literal[
    "mdf",
    "hardware",
    "profile",
    "accessory",
    "finish",
    "service",
    "other",
]
InterpretationSource = Literal["openai", "assisted_local"]


class QuoteAIUnavailable(RuntimeError):
    """Compatibilidade para integrações antigas que tratavam indisponibilidade externa."""


class StructuredBriefModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_max_length=2000)


class QuoteBriefItem(StructuredBriefModel):
    name: str = Field(min_length=1, max_length=200)
    environment: str | None = Field(default=None, max_length=100)
    furniture_type: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    materials: list[str] = Field(default_factory=list, max_length=30)
    thicknesses_mm: list[Annotated[float, Field(gt=0, le=200)]] = Field(default_factory=list, max_length=20)
    finishes: list[str] = Field(default_factory=list, max_length=30)
    hardware: list[str] = Field(default_factory=list, max_length=30)
    accessories: list[str] = Field(default_factory=list, max_length=30)
    services: list[str] = Field(default_factory=list, max_length=30)
    complexity: Literal["low", "medium", "high", "unknown"] = "unknown"
    observations: list[str] = Field(default_factory=list, max_length=30)
    quantity: float = Field(default=1, gt=0, le=1000)
    width_m: float | None = Field(default=None, gt=0, le=100)
    height_m: float | None = Field(default=None, gt=0, le=100)
    depth_m: float | None = Field(default=None, gt=0, le=100)
    doors: int | None = Field(default=None, ge=0, le=1000)
    drawers: int | None = Field(default=None, ge=0, le=1000)


class QuoteRequirement(StructuredBriefModel):
    name: str = Field(min_length=1, max_length=180)
    kind: MaterialKind
    quantity: float = Field(gt=0, le=100000)
    unit: str = Field(min_length=1, max_length=30)


class QuoteBrief(StructuredBriefModel):
    normalized_description: str = Field(min_length=3, max_length=3000)
    measurements_summary: str | None = Field(default=None, max_length=2000)
    materials_summary: str | None = Field(default=None, max_length=2000)
    items: list[QuoteBriefItem] = Field(default_factory=list, max_length=100)
    requirements: list[QuoteRequirement] = Field(default_factory=list, max_length=300)
    finish: str | None = Field(default=None, max_length=500)
    missing_data: list[str] = Field(default_factory=list, max_length=30)
    risks: list[str] = Field(default_factory=list, max_length=30)
    questions: list[str] = Field(default_factory=list, max_length=30)
    confidence_score: int = Field(ge=0, le=100)


class QuoteBriefInterpretation(BaseModel):
    source: InterpretationSource
    fallback_reason: str | None = None
    brief: QuoteBrief


class CatalogMaterial(BaseModel):
    id: int = Field(gt=0)
    name: str
    kind: MaterialKind
    unit: str
    unit_cost: Decimal = Field(ge=0)
    waste_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class PricedRequirement(BaseModel):
    requirement: QuoteRequirement
    material_id: int
    catalog_name: str
    unit_cost: Decimal
    waste_percent: Decimal
    total_cost: Decimal


class UnpricedRequirement(BaseModel):
    requirement: QuoteRequirement
    reason: str


class QuotePreview(BaseModel):
    brief: QuoteBrief
    interpretation_source: InterpretationSource = "openai"
    fallback_reason: str | None = None
    priced_items: list[PricedRequirement]
    unpriced_items: list[UnpricedRequirement]
    material_cost: Decimal
    hardware_cost: Decimal
    labor_cost: Decimal
    finishing_cost: Decimal
    base_cost: Decimal
    profit_margin: Decimal
    suggested_total: Decimal
    requires_approval: bool = True


def _normalized(value: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    return " ".join(without_accents.casefold().split())


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _catalog_match(
    requirement: QuoteRequirement,
    catalog: Sequence[CatalogMaterial],
) -> tuple[CatalogMaterial | None, str | None]:
    same_kind = [item for item in catalog if item.kind == requirement.kind]
    requirement_name = _normalized(requirement.name)
    exact = [item for item in same_kind if _normalized(item.name) == requirement_name]
    candidates = exact
    if not candidates:
        candidates = [
            item
            for item in same_kind
            if requirement_name in _normalized(item.name)
            or _normalized(item.name) in requirement_name
        ]
    if not candidates:
        return None, "Insumo não encontrado no catálogo"

    compatible = [
        item for item in candidates if _normalized(item.unit) == _normalized(requirement.unit)
    ]
    if not compatible:
        return None, "Unidade incompatível com o catálogo"
    if len(compatible) != 1:
        return None, "Correspondência ambígua no catálogo"
    return compatible[0], None


def build_quote_preview(
    brief: QuoteBrief,
    catalog: Sequence[CatalogMaterial],
    *,
    profit_margin: Decimal,
    interpretation_source: InterpretationSource = "openai",
    fallback_reason: str | None = None,
) -> QuotePreview:
    buckets = {
        "material_cost": Decimal("0"),
        "hardware_cost": Decimal("0"),
        "labor_cost": Decimal("0"),
        "finishing_cost": Decimal("0"),
    }
    priced: list[PricedRequirement] = []
    unpriced: list[UnpricedRequirement] = []

    for requirement in brief.requirements:
        material, reason = _catalog_match(requirement, catalog)
        if material is None:
            unpriced.append(
                UnpricedRequirement(requirement=requirement, reason=reason or "Sem preço")
            )
            continue

        quantity = Decimal(str(requirement.quantity))
        waste_multiplier = Decimal("1") + material.waste_percent / Decimal("100")
        total_cost = _money(quantity * material.unit_cost * waste_multiplier)
        priced.append(
            PricedRequirement(
                requirement=requirement,
                material_id=material.id,
                catalog_name=material.name,
                unit_cost=_money(material.unit_cost),
                waste_percent=material.waste_percent,
                total_cost=total_cost,
            )
        )

        if material.kind == "service":
            bucket = "labor_cost"
        elif material.kind == "finish":
            bucket = "finishing_cost"
        elif material.kind in {"hardware", "profile", "accessory"}:
            bucket = "hardware_cost"
        else:
            bucket = "material_cost"
        buckets[bucket] += total_cost

    pricing = calculate_quote_suggestion(
        material_cost=buckets["material_cost"],
        hardware_cost=buckets["hardware_cost"],
        labor_cost=buckets["labor_cost"],
        finishing_cost=buckets["finishing_cost"],
        profit_margin=profit_margin,
    )
    return QuotePreview(
        brief=brief,
        interpretation_source=interpretation_source,
        fallback_reason=fallback_reason,
        priced_items=priced,
        unpriced_items=unpriced,
        **pricing,
    )


def _local_quote_brief(
    request_text: str,
    catalog: Sequence[CatalogMaterial],
) -> QuoteBrief:
    """Fallback seguro: organiza o pedido sem inventar quantidades ou preços."""
    description = " ".join(request_text.split())[:3000]
    normalized_request = _normalized(description)

    number = r"[0-9]{1,3}(?:[.,][0-9]{1,3})?"
    unit = r"(?:mm|cm|m)?"
    gap = r"\s{0,4}"
    measurement_pattern = re.compile(
        rf"{number}{gap}{unit}{gap}[x\u00d7]{gap}{number}{gap}{unit}"
        rf"(?:{gap}[x\u00d7]{gap}{number}{gap}{unit})?",
        re.IGNORECASE,
    )
    measurements = [match.group(0).strip() for match in measurement_pattern.finditer(description)]
    measurements_summary = "; ".join(dict.fromkeys(measurements[:6])) or None

    material_names: list[str] = []
    for item in list(catalog)[:300]:
        candidate = _normalized(item.name)
        if candidate and candidate in normalized_request and item.name not in material_names:
            material_names.append(item.name)
        if len(material_names) >= 12:
            break

    generic_materials = (
        "MDF",
        "MDP",
        "compensado",
        "madeira",
        "alumínio",
        "vidro",
        "ferragens",
        "dobradiça",
        "corrediça",
        "puxador",
    )
    for material in generic_materials:
        if _normalized(material) in normalized_request and material not in material_names:
            material_names.append(material)
    materials_summary = ", ".join(material_names[:12]) or None

    finish = next(
        (
            finish_name
            for finish_name in ("laca", "fosco", "brilho", "acetinado", "verniz")
            if _normalized(finish_name) in normalized_request
        ),
        None,
    )

    questions = [
        "Confirme as medidas finais antes de liberar o orçamento.",
        "Revise materiais, ferragens e acabamento antes da aprovação.",
        "Interpretação assistida local ativa; conecte a IA externa para uma leitura técnica mais detalhada.",
    ]
    if measurements_summary is None:
        questions.insert(0, "Informe largura, altura e profundidade sempre que possível.")
    if materials_summary is None:
        questions.insert(1, "Informe os materiais desejados pelo cliente.")

    return QuoteBrief(
        normalized_description=description,
        measurements_summary=measurements_summary,
        materials_summary=materials_summary,
        items=[QuoteBriefItem(name="Móvel planejado", quantity=1)],
        requirements=[],
        finish=finish,
        missing_data=(["Medidas finais"] if measurements_summary is None else []) + (["Materiais"] if materials_summary is None else []) + ["Quantidades técnicas e custos"],
        risks=["Conferir o projeto técnico antes de aprovar; o pedido não é uma lista de corte."],
        questions=questions,
        confidence_score=35 if measurements_summary else 25,
    )


def _local_interpretation(
    request_text: str,
    catalog: Sequence[CatalogMaterial],
) -> QuoteBriefInterpretation:
    return QuoteBriefInterpretation(
        source="assisted_local",
        brief=_local_quote_brief(request_text, catalog),
    )


def extract_quote_brief_result(
    request_text: str,
    *,
    db: Session | None = None,
    tenant_id: int | None = None,
    catalog: Sequence[CatalogMaterial] = (),
) -> QuoteBriefInterpretation:
    """Interpreta somente dados técnicos; qualquer erro mantém o fallback local."""
    completion = structured_completion(
        operation="quote_brief", schema=QuoteBrief, db=db, tenant_id=tenant_id,
        instructions=("Extraia ambiente, tipo de móvel, descrição, quantidade, medidas em metros, "
                      "materiais, espessuras em mm, acabamentos, ferragens, acessórios, complexidade, "
                      "serviços e observações. Liste dados faltantes, riscos e perguntas. "
                      "Use catálogo apenas quando houver correspondência clara; inferências exigem confirmação."),
        data={"customer_request": request_text, "catalog": [
            {"name": item.name, "kind": item.kind, "unit": item.unit} for item in list(catalog)[:300]
        ]},
    )
    if completion.value is not None:
        return QuoteBriefInterpretation(source="openai", brief=completion.value)
    return QuoteBriefInterpretation(source="assisted_local", brief=_local_quote_brief(request_text, catalog),
                                    fallback_reason=completion.error_code)


def extract_quote_brief(
    request_text: str,
    *,
    catalog: Sequence[CatalogMaterial] = (),
) -> QuoteBrief:
    """Compatibilidade: retorna somente o briefing estruturado."""
    return extract_quote_brief_result(request_text, catalog=catalog).brief
