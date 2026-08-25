import json
import os
from datetime import datetime, timezone
from decimal import Decimal


def _local_analysis(*, base_cost: Decimal, suggested_total: Decimal, profit_margin: Decimal) -> str:
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
    return json.dumps({
        "source": "local-analysis",
        "summary": "Análise determinística de segurança financeira do orçamento.",
        "warnings": warnings,
        "recommendations": recommendations,
        "financial_values_locked": True,
    }, ensure_ascii=False)


def analyze_quote(*, base_cost: Decimal, suggested_total: Decimal, profit_margin: Decimal) -> dict[str, object]:
    """Analisa o orçamento. A análise nunca altera valores financeiros."""
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

    result: dict[str, object] = {
        "base_cost": base_cost,
        "suggested_total": suggested_total,
        "profit_margin": profit_margin,
        "warnings": warnings,
        "recommendations": recommendations,
        "ai_analysis": _local_analysis(base_cost=base_cost, suggested_total=suggested_total, profit_margin=profit_margin),
        "ai_analyzed_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "requires_approval": True,
    }

    api_key = os.getenv("OPENAI_API_KEY")
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
                    }, ensure_ascii=False),
                },
            ],
        )
        if response.output_text:
            result["ai_analysis"] = response.output_text
            result["ai_analyzed_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    except Exception:
        # A análise local permanece disponível; falha do provedor externo não quebra o orçamento.
        pass

    return result
