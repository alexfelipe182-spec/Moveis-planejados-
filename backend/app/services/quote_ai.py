import json
import os
from decimal import Decimal


def analyze_quote(
    *,
    base_cost: Decimal,
    suggested_total: Decimal,
    profit_margin: Decimal,
) -> dict[str, object]:
    """Analisa o orçamento sem permitir que a IA altere valores financeiros."""
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

    result: dict[str, object] = {
        "base_cost": base_cost,
        "suggested_total": suggested_total,
        "profit_margin": profit_margin,
        "warnings": warnings,
        "recommendations": recommendations,
        "ai_analysis": None,
        "requires_approval": True,
    }

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return result

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
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
                    "content": json.dumps(
                        {
                            "base_cost": str(base_cost),
                            "suggested_total": str(suggested_total),
                            "profit_margin": str(profit_margin),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        result["ai_analysis"] = response.output_text
    except Exception:
        result["ai_analysis"] = None

    return result
