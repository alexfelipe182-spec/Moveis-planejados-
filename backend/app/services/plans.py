from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PlanDefinition:
    code: str
    name: str
    monthly_price_brl: int
    max_users: int
    max_active_projects: int
    features: tuple[str, ...]


PLANS = {
    "starter": PlanDefinition(
        code="starter",
        name="Starter",
        monthly_price_brl=149,
        max_users=3,
        max_active_projects=100,
        features=("clientes", "orcamentos", "projetos", "producao", "custos"),
    ),
    "professional": PlanDefinition(
        code="professional",
        name="Professional",
        monthly_price_brl=299,
        max_users=10,
        max_active_projects=1000,
        features=(
            "clientes",
            "orcamentos",
            "projetos",
            "producao",
            "custos",
            "inteligencia_preditiva",
            "automacoes",
        ),
    ),
    "business": PlanDefinition(
        code="business",
        name="Business",
        monthly_price_brl=599,
        max_users=50,
        max_active_projects=10000,
        features=(
            "clientes",
            "orcamentos",
            "projetos",
            "producao",
            "custos",
            "inteligencia_preditiva",
            "automacoes",
            "relatorios_avancados",
            "suporte_prioritario",
        ),
    ),
}


def public_plan_catalog() -> list[dict]:
    return [asdict(plan) for plan in PLANS.values()]


def get_plan(code: str) -> PlanDefinition:
    try:
        return PLANS[code]
    except KeyError as exc:
        raise ValueError("Plano inválido") from exc
