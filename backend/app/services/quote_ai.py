import json
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.services.openai_config import structured_completion


class QuoteCommentary(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=2000)
    summary: str = Field(min_length=1, max_length=2000)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    recommendations: list[str] = Field(default_factory=list, max_length=30)
    commercial_questions: list[str] = Field(default_factory=list, max_length=30)


def _financial_signals(*, base_cost: Decimal, suggested_total: Decimal, profit_margin: Decimal) -> dict[str, object]:
    projected_profit = max(Decimal("0"), suggested_total - base_cost)
    markup = Decimal("0") if base_cost <= 0 else (suggested_total / base_cost - Decimal("1")) * Decimal("100")
    risk_points = 0
    if base_cost <= 0:
        risk_points += 45
    if suggested_total <= base_cost and base_cost > 0:
        risk_points += 45
    if profit_margin < 15:
        risk_points += 35
    elif profit_margin < 20:
        risk_points += 20
    elif profit_margin >= 60:
        risk_points += 10
    risk_score = min(100, risk_points)
    if risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 25:
        risk_level = "medium"
    else:
        risk_level = "low"
    confidence = 55 if base_cost <= 0 else 90
    return {
        "projected_profit": projected_profit.quantize(Decimal("0.01")),
        "markup_percent": markup.quantize(Decimal("0.01")),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "confidence_score": confidence,
    }


def _local_analysis(*, base_cost: Decimal, suggested_total: Decimal, profit_margin: Decimal) -> str:
    warnings: list[str] = []
    recommendations: list[str] = []
    signals = _financial_signals(
        base_cost=base_cost,
        suggested_total=suggested_total,
        profit_margin=profit_margin,
    )
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
    if signals["risk_level"] == "high":
        recommendations.append("Exija revisão humana antes de liberar esta proposta comercial.")
    return json.dumps(
        {
            "source": "local-analysis",
            "summary": "Análise determinística de segurança financeira do orçamento.",
            "warnings": warnings,
            "recommendations": recommendations,
            "risk_score": signals["risk_score"],
            "risk_level": signals["risk_level"],
            "confidence_score": signals["confidence_score"],
            "financial_values_locked": True,
        },
        ensure_ascii=False,
    )


def analyze_quote(*, base_cost: Decimal, suggested_total: Decimal, profit_margin: Decimal,
                  db: Session | None = None, tenant_id: int | None = None, use_provider: bool = True) -> dict[str, object]:
    """Analisa risco e qualidade do orçamento sem permitir que a IA altere valores financeiros."""
    warnings: list[str] = []
    recommendations: list[str] = []
    signals = _financial_signals(
        base_cost=base_cost,
        suggested_total=suggested_total,
        profit_margin=profit_margin,
    )
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
        "projected_profit": signals["projected_profit"],
        "markup_percent": signals["markup_percent"],
        "risk_score": signals["risk_score"],
        "risk_level": signals["risk_level"],
        "confidence_score": signals["confidence_score"],
        "warnings": warnings,
        "recommendations": recommendations,
        "ai_analysis": _local_analysis(base_cost=base_cost, suggested_total=suggested_total, profit_margin=profit_margin),
        "ai_analyzed_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "requires_approval": True,
    }

    result["interpretation_source"] = "assisted_local"
    result["fallback_reason"] = None
    if not use_provider:
        return result
    completion = structured_completion(
        operation="quote_analysis", instructions="Avalie riscos e perguntas comerciais. Os valores recebidos são imutáveis.",
        data={"financial_snapshot": {key: str(result[key]) for key in
              ("base_cost", "suggested_total", "profit_margin", "risk_score", "risk_level")}},
        schema=QuoteCommentary, db=db, tenant_id=tenant_id,
    )
    result["fallback_reason"] = completion.error_code
    if completion.value is not None:
        result["interpretation_source"] = "openai"
        commentary = completion.value.model_dump()
        # Preserve all deterministic warnings; the provider can only add commentary.
        commentary["warnings"] = list(dict.fromkeys(warnings + commentary["warnings"]))
        commentary["recommendations"] = list(dict.fromkeys(recommendations + commentary["recommendations"]))
        result["warnings"] = commentary["warnings"]
        result["recommendations"] = commentary["recommendations"]
        result["ai_analysis"] = json.dumps({"source": "openai", "financial_values_locked": True, **commentary}, ensure_ascii=False)
    return result
