from decimal import Decimal


def analyze_quote(
    *,
    base_cost: Decimal,
    suggested_total: Decimal,
    profit_margin: Decimal,
) -> dict[str, object]:
    """Retorna uma análise determinística e segura antes da integração com um provedor de IA."""
    warnings: list[str] = []
    recommendations: list[str] = []

    if base_cost <= 0:
        warnings.append("O orçamento ainda não possui custos cadastrados.")
        recommendations.append("Cadastre materiais, ferragens, mão de obra e acabamento antes de enviar ao cliente.")
    if profit_margin < 20:
        warnings.append("A margem de lucro está abaixo de 20%.")
        recommendations.append("Revise a margem antes da aprovação do orçamento.")
    elif profit_margin >= 50:
        recommendations.append("Confirme se a margem elevada está adequada ao posicionamento e ao mercado.")

    return {
        "base_cost": base_cost,
        "suggested_total": suggested_total,
        "profit_margin": profit_margin,
        "warnings": warnings,
        "recommendations": recommendations,
        "requires_approval": True,
    }
