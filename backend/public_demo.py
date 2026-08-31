"""Public, disposable homologation app with synthetic data only.

This entrypoint is intentionally isolated from every configured database and
provider. It can only boot inside Render when PUBLIC_DEMO=1 is explicit.
"""

import asyncio
import os
from pathlib import Path


if os.getenv("PUBLIC_DEMO") != "1" or os.getenv("RENDER") != "true":
    raise RuntimeError("Public demo requires PUBLIC_DEMO=1 inside Render")

# Never let this demonstration contact a real database, Redis, email, billing
# or external AI provider, even if the service inherits unexpected variables.
os.environ["ENVIRONMENT"] = "production"
os.environ["DATABASE_URL"] = "postgresql+psycopg://demo:unused@unused.invalid:5432/demo"
os.environ["REDIS_URL"] = "redis://unused.invalid:6379/15"
os.environ["EMAIL_PROVIDER"] = "disabled"
os.environ["BILLING_PROVIDER"] = "sandbox"
os.environ["OPENAI_API_KEY"] = ""
for setting in (
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "EMAIL_FROM",
    "RESEND_API_KEY",
    "BILLING_WEBHOOK_SECRET",
):
    os.environ[setting] = ""

from fastapi.responses import HTMLResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.main as main_module  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    Customer,
    Material,
    Organization,
    Plan,
    Project,
    Subscription,
    Supplier,
    User,
)


FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
database = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(database)
sessions = sessionmaker(database, expire_on_commit=False)


def seed_demo() -> None:
    with sessions() as db:
        organization = Organization(
            name="Multi-Marcenarias — Homologação",
            slug="multi-marcenarias-demo",
            status="active",
        )
        plans = [
            Plan(
                code="starter",
                name="Essencial",
                monthly_price_cents=4900,
                max_users=3,
                features={"customers": True, "quotes": True, "projects": True, "production": True, "costs": True},
            ),
            Plan(
                code="pro",
                name="Profissional",
                monthly_price_cents=9900,
                max_users=10,
                features={
                    "customers": True,
                    "quotes": True,
                    "projects": True,
                    "production": True,
                    "costs": True,
                    "intelligence": True,
                    "automation": True,
                    "profitability": True,
                },
            ),
            Plan(
                code="scale",
                name="Empresarial",
                monthly_price_cents=24900,
                max_users=50,
                features={
                    "customers": True,
                    "quotes": True,
                    "projects": True,
                    "production": True,
                    "costs": True,
                    "intelligence": True,
                    "automation": True,
                    "profitability": True,
                    "advanced_reports": True,
                    "priority_support": True,
                    "assisted_onboarding": True,
                },
            ),
        ]
        db.add_all([organization, *plans])
        db.flush()
        db.add(
            User(
                organization_id=organization.id,
                name="Cliente de apresentação",
                email="cliente.demo@example.com",
                password_hash=hash_password("MultiCliente-2026!"),
                is_admin=True,
                is_platform_admin=False,
            )
        )
        db.add(
            Subscription(
                organization_id=organization.id,
                plan_id=plans[1].id,
                status="trial",
                provider="sandbox",
            )
        )
        db.add(
            Category(
                organization_id=organization.id,
                name="Cozinhas de demonstração",
                description="Categoria sintética para apresentação",
            )
        )
        customers = [
            Customer(
                organization_id=organization.id,
                name=f"Cliente de teste {number:03}",
                email=f"preview-{number}@example.com",
            )
            for number in range(1, 126)
        ]
        db.add_all(customers)
        db.flush()
        supplier = Supplier(
            organization_id=organization.id,
            name="Fornecedor de demonstração",
            notes="Cadastro sintético; nenhum pedido real.",
        )
        db.add(supplier)
        db.flush()
        db.add(
            Material(
                organization_id=organization.id,
                name="MDF de demonstração",
                kind="mdf",
                supplier_id=supplier.id,
                unit="chapa",
                unit_cost=300,
                waste_percent=10,
            )
        )
        db.add(
            Project(
                organization_id=organization.id,
                name="Cozinha Aurora — DEMONSTRAÇÃO",
                description="Projeto fictício para apresentação ao cliente.",
                customer_id=customers[-1].id,
                status="planning",
            )
        )
        db.commit()


seed_demo()


class DemoRedis:
    async def incr(self, _key):
        raise ConnectionError("Public demo uses in-process rate protection")

    async def ping(self):
        return True

    async def aclose(self):
        return None


demo_db_lock = asyncio.Lock()


async def isolated_db():
    # StaticPool owns one in-memory connection; serialize requests for safety.
    async with demo_db_lock:
        with sessions() as db:
            yield db


main_module.engine = database
main_module.rate_limiter.redis = DemoRedis()
main_module.rate_limiter.limit = 10_000
app = main_module.app
app.dependency_overrides[get_db] = isolated_db
app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/"]


@app.get("/", include_in_schema=False)
def demo_home():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    banner = (
        '<div style="background:#fff3cc;color:#362b08;padding:8px;text-align:center" '
        'role="status">AMBIENTE DE HOMOLOGAÇÃO — dados sintéticos, sem envio de mensagens '
        "ou cobranças</div>"
    )
    html = html.replace("<body>", "<body>" + banner, 1)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/site-config.js", include_in_schema=False)
def demo_configuration():
    content = "window.API_BASE_URL = window.location.origin + '/api/v1';\n"
    return Response(
        content + (FRONTEND / "site-config.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="demo-static")
