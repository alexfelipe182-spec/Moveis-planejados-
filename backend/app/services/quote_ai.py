import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal


_FINANCIAL_VALUE_PATTERN = re.compile(
    r"(?:r\s*\$|[$€£]|(?:preç[oa]|valor|custo|margem)[^.\n]{0,60}\d|\d[^.\n]{0,60}(?:preç[oa]|valor|custo|margem)|(?:preç[oa]|valor|custo|margem)[^.\n]{0,60}\b(?:real|reais|dólar|dólares|euro|euros)\b)",
    re.IGNORECASE,
)
_MAX_EXTERNAL_RESPONSE_CHARS = 20_000
_EXTERNAL_ANALYSIS_FIELDS = {"summary", "warnings", "recommendations"}


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _context_value(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value.strip()[:limit]


def _rule_based_insights(
    *,
    base_cost: Decimal,
    suggested_total: Decimal,
    profit_margin: Decimal,
    description: str | None = None,
    measurements: str | None = None,
    materials: str | None = None,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    recommendations: list[str] = []
    if base_cost <= 0:
        warnings.append("O orçamento ainda não possui custos cadastrados.")
        recommendations.append("Cadastre os custos antes de enviar ao cliente.")
    if profit_margin < 20:
        warnings.append("A margem de lucro está abaixo de 20%.")
        recommendations.append("Revise a margem antes da aprovação.")
    elif profit_margin >= 50:
        recommendations.append("Confirme se a margem elevada está adequada ao mercado.")
    if suggested_total <= base_cost and base_cost > 0:
        warnings.append("O preço sugerido não supera o custo-base.")
        recommendations.append("Revise a margem e os custos antes da aprovação.")
    context_supplied = any(value is not None for value in (description, measurements, materials))
    if context_supplied and not (measurements or "").strip():
        warnings.append("As medidas do projeto ainda não foram informadas.")
        recommendations.append("Confirme largura, altura e profundidade antes de aprovar.")
    if context_supplied and not (materials or "").strip():
        warnings.append("Os materiais do projeto ainda não foram informados.")
        recommendations.append("Defina materiais, espessuras e acabamentos antes de enviar ao cliente.")
    return _unique(warnings), _unique(recommendations)


def _analysis_document(*, source: str, summary: str, warnings: list[str], recommendations: list[str]) -> str:
    return json.dumps({
        "source": source,
        "summary": summary,
        "warnings": warnings,
        "recommendations": recommendations,
        "financial_values_locked": True,
    }, ensure_ascii=False)


def _clean_external_text(value: str, limit: int) -> str:
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in value):
        raise ValueError("A análise externa retornou caracteres de controle")
    return " ".join(value.split())[:limit]


def _validated_external_analysis(text: str) -> tuple[str, list[str], list[str]]:
    if len(text) > _MAX_EXTERNAL_RESPONSE_CHARS:
        raise ValueError("A análise externa excedeu o limite de tamanho")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("A análise externa não retornou um objeto JSON")
    if set(parsed) != _EXTERNAL_ANALYSIS_FIELDS:
        raise ValueError("A análise externa não respeitou os campos obrigatórios")
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("A análise externa não retornou um resumo válido")

    def text_list(name: str) -> list[str]:
        values = parsed.get(name, [])
        if not isinstance(values, list):
            raise ValueError(f"A análise externa não retornou {name} como lista")
        if any(not isinstance(item, str) for item in values):
            raise ValueError(f"A análise externa retornou itens inválidos em {name}")
        return _unique([
            _clean_external_text(item, 300)
            for item in values[:10]
            if item.strip()
        ])

    validated = _clean_external_text(summary, 800), text_list("warnings"), text_list("recommendations")
    if any(_FINANCIAL_VALUE_PATTERN.search(item) for item in (validated[0], *validated[1], *validated[2])):
        raise ValueError("A análise externa tentou publicar um valor financeiro")
    return validated


def analyze_quote(
    *,
    base_cost: Decimal,
    suggested_total: Decimal,
    profit_margin: Decimal,
    description: str | None = None,
    measurements: str | None = None,
    materials: str | None = None,
) -> dict[str, object]:
    """Analisa o orçamento. A análise nunca altera valores financeiros."""
    description = _context_value(description, 3000)
    measurements = _context_value(measurements, 2000)
    materials = _context_value(materials, 2000)
    warnings, recommendations = _rule_based_insights(
        base_cost=base_cost,
        suggested_total=suggested_total,
        profit_margin=profit_margin,
        description=description,
        measurements=measurements,
        materials=materials,
    )
    local_summary = "Análise determinística de segurança financeira e completude técnica do orçamento."

    result: dict[str, object] = {
        "base_cost": base_cost,
        "suggested_total": suggested_total,
        "profit_margin": profit_margin,
        "warnings": warnings,
        "recommendations": recommendations,
        "analysis_source": "local-analysis",
        "summary": local_summary,
        "ai_analysis": _analysis_document(
            source="local-analysis",
            summary=local_summary,
            warnings=warnings,
            recommendations=recommendations,
        ),
        "ai_analyzed_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "requires_approval": True,
    }

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return result

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=10.0, max_retries=1)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            input=[
                {
                    "role": "system",
                    "content": (
                        "Você é um analista de orçamentos para marcenaria. "
                        "Analise riscos e faça recomendações. Nunca altere, calcule ou invente preços. "
                        "Responda somente JSON com campos summary, warnings e recommendations."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "base_cost": str(base_cost),
                        "suggested_total": str(suggested_total),
                        "profit_margin": str(profit_margin),
                        "description": description,
                        "measurements": measurements,
                        "materials": materials,
                    }, ensure_ascii=False),
                },
            ],
        )
        if not response.output_text:
            raise ValueError("A análise externa retornou uma resposta vazia")
        summary, external_warnings, external_recommendations = _validated_external_analysis(response.output_text)
        result["warnings"] = _unique(warnings + external_warnings)
        result["recommendations"] = _unique(recommendations + external_recommendations)
        result["analysis_source"] = "openai-assisted"
        result["summary"] = summary
        result["ai_analysis"] = _analysis_document(
            source="openai-assisted",
            summary=summary,
            warnings=result["warnings"],
            recommendations=result["recommendations"],
        )
        result["ai_analyzed_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    except Exception:
        # A análise local permanece disponível; falha do provedor externo não quebra o orçamento.
        result["analysis_source"] = "local-fallback"
        result["summary"] = local_summary
        result["warnings"] = warnings
        result["recommendations"] = recommendations
        result["ai_analysis"] = _analysis_document(
            source="local-fallback",
            summary=local_summary,
            warnings=warnings,
            recommendations=recommendations,
        )

    return result
