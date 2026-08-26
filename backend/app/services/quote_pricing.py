from decimal import Decimal, ROUND_HALF_UP


MONEY = Decimal("0.01")


def _decimal(value: Decimal | int | float | str) -> Decimal:
    """Normalize supported numeric inputs without introducing float artifacts."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    """Round monetary values to cents using conventional financial rounding."""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_quote_suggestion(
    material_cost: Decimal | int | float | str = Decimal("0"),
    hardware_cost: Decimal | int | float | str = Decimal("0"),
    labor_cost: Decimal | int | float | str = Decimal("0"),
    finishing_cost: Decimal | int | float | str = Decimal("0"),
    profit_margin: Decimal | int | float | str = Decimal("30"),
) -> dict[str, Decimal]:
    material_cost = _decimal(material_cost)
    hardware_cost = _decimal(hardware_cost)
    labor_cost = _decimal(labor_cost)
    finishing_cost = _decimal(finishing_cost)
    profit_margin = _decimal(profit_margin)

    values = [material_cost, hardware_cost, labor_cost, finishing_cost]
    if any(value < 0 for value in values):
        raise ValueError("Os custos não podem ser negativos")
    if profit_margin < 0 or profit_margin > 100:
        raise ValueError("A margem de lucro deve estar entre 0 e 100")

    base_cost = sum(values, Decimal("0"))
    suggested_total = base_cost * (Decimal("1") + profit_margin / Decimal("100"))

    return {
        "material_cost": _money(material_cost),
        "hardware_cost": _money(hardware_cost),
        "labor_cost": _money(labor_cost),
        "finishing_cost": _money(finishing_cost),
        "base_cost": _money(base_cost),
        "profit_margin": _money(profit_margin),
        "suggested_total": _money(suggested_total),
    }
