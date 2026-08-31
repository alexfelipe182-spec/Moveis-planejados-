from decimal import Decimal, ROUND_HALF_UP


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recommend_from_history(
    *,
    base_cost: Decimal,
    requested_margin: Decimal,
    historical_markups: list[Decimal],
    historical_cost_variances: list[Decimal],
) -> dict[str, Decimal | int | str]:
    """Recommend markup from realized tenant history without changing prices automatically."""
    sample_size = len(historical_markups)
    if sample_size == 0:
        recommended_margin = max(requested_margin, Decimal("25"))
        average_markup = Decimal("0")
        average_variance = Decimal("0")
        confidence = "low"
    else:
        average_markup = sum(historical_markups, Decimal("0")) / Decimal(sample_size)
        average_variance = (
            sum(historical_cost_variances, Decimal("0")) / Decimal(len(historical_cost_variances))
            if historical_cost_variances
            else Decimal("0")
        )
        recommended_margin = max(requested_margin, average_markup + max(average_variance, Decimal("0")))
        confidence = "high" if sample_size >= 10 else "medium" if sample_size >= 3 else "low"

    recommended_margin = min(max(recommended_margin, Decimal("5")), Decimal("80"))
    recommended_total = base_cost * (Decimal("1") + recommended_margin / Decimal("100"))
    risk_score = Decimal("20")
    if sample_size == 0:
        risk_score += Decimal("25")
    if average_variance > 0:
        risk_score += min(average_variance * Decimal("1.5"), Decimal("35"))
    if requested_margin < recommended_margin:
        risk_score += min((recommended_margin - requested_margin) * Decimal("1.5"), Decimal("20"))
    risk_score = min(max(risk_score, Decimal("0")), Decimal("100"))
    risk_level = "high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low"
    return {
        "sample_size": sample_size,
        "average_real_markup_percent": _q(average_markup),
        "average_cost_variance_percent": _q(average_variance),
        "requested_margin_percent": _q(requested_margin),
        "recommended_margin_percent": _q(recommended_margin),
        "recommended_total": _q(recommended_total),
        "risk_score": int(_q(risk_score)),
        "risk_level": risk_level,
        "confidence": confidence,
    }
