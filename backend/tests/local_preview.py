"""Explicitly opt-in, loopback-only browser preview with disposable synthetic data.

Run from backend with IDEAL_LOCAL_PREVIEW=1 and ENVIRONMENT=test:
python -m uvicorn local_preview:app --app-dir tests --host 127.0.0.1 --port 8765
Never run this entrypoint on a public interface or in production.
"""

import asyncio
import os
import secrets
from pathlib import Path

if os.getenv("IDEAL_LOCAL_PREVIEW") != "1" or os.getenv("ENVIRONMENT") != "test" or os.getenv("RENDER"):
    raise RuntimeError("Preview requires IDEAL_LOCAL_PREVIEW=1, ENVIRONMENT=test and no Render environment")

# No provider credentials, external mail, external AI or real database access.
os.environ["DATABASE_URL"] = "postgresql+psycopg://preview:unused@127.0.0.1:5432/unused_preview"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/15"
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["OPENAI_API_KEY"] = ""
os.environ["EMAIL_PROVIDER"] = "disabled"
os.environ["BILLING_PROVIDER"] = "sandbox"
for setting in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "EMAIL_FROM", "RESEND_API_KEY"):
    # An explicit empty value prevents Pydantic from loading a real .env secret.
    os.environ[setting] = ""

from fastapi.responses import HTMLResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.main as main_module  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models import Category, Customer, Material, Organization, Plan, Project, Subscription, Supplier, User  # noqa: E402


FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
database = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(database)
sessions = sessionmaker(database, expire_on_commit=False)
with sessions() as db:
    db.add(Organization(id=1, name="Multi-Marcenarias — Prévia", slug="previa", status="active"))
    db.add(Plan(id=1, code="starter", name="Essencial", monthly_price_cents=4900, max_users=3, features={"quotes": True, "production": True}))
    db.add(Plan(id=2, code="pro", name="Profissional", monthly_price_cents=9900, max_users=10, features={"quotes": True, "production": True, "intelligence": True, "automation": True, "profitability": True}))
    db.flush()
    db.add(User(organization_id=1, name="Equipe de teste", email="preview@example.com", password_hash=hash_password("Preview-local-123!"), is_admin=True, is_platform_admin=True))
    db.add(User(organization_id=1, name="Cliente de apresentação", email="cliente.demo@example.com", password_hash=hash_password("MultiCliente-2026!"), is_admin=True, is_platform_admin=False))
    db.add(Subscription(organization_id=1, plan_id=2, status="trial", provider="sandbox"))
    db.add(Category(organization_id=1, name="Cozinhas de teste", description="Categoria sintética"))
    db.add_all([
        Customer(organization_id=1, name=f"Cliente de teste {number:03}", email=f"preview-{number}@example.com")
        for number in range(1, 126)
    ])
    db.commit()
    supplier = Supplier(organization_id=1, name="Fornecedor de demonstração")
    db.add(supplier)
    db.flush()
    db.add(Material(organization_id=1, name="MDF de demonstração", kind="mdf", supplier_id=supplier.id, unit_cost=100, waste_percent=10))
    db.add(Project(organization_id=1, name="Cozinha de demonstração", customer_id=125, status="planning"))
    db.commit()


class LocalRedis:
    async def incr(self, _key):
        raise ConnectionError("Local preview uses in-process rate protection")

    async def ping(self):
        return True

    async def aclose(self):
        pass


preview_db_lock = asyncio.Lock()


async def isolated_db():
    # SQLite's single in-memory connection cannot run concurrent requests safely.
    # This serialization is preview-only; production uses PostgreSQL connections.
    async with preview_db_lock:
        with sessions() as db:
            yield db


main_module.engine = database
main_module.rate_limiter.redis = LocalRedis()
main_module.rate_limiter.limit = 10_000
app = main_module.app
app.dependency_overrides[get_db] = isolated_db
app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/"]


@app.get("/", include_in_schema=False)
def preview_home():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for asset in FRONTEND.glob("*.js"):
        html = html.replace(f'src="./{asset.name}"', f'src="./{asset.name}?v={asset.stat().st_mtime_ns}"')
    banner = '<div style="background:#fff3cc;color:#362b08;padding:8px;text-align:center" role="status">AMBIENTE DE TESTE — dados sintéticos, sem envio de mensagens</div>'
    if '<body class="dark">' in html:
        html = html.replace('<body class="dark">', '<body class="dark">' + banner, 1)
    else:
        html = html.replace('<body>', '<body>' + banner, 1)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/site-config.js", include_in_schema=False)
def preview_configuration():
    content = "window.API_BASE_URL = window.location.origin + '/api/v1';\n"
    return Response(content + (FRONTEND / "site-config.js").read_text(encoding="utf-8"), media_type="application/javascript")


app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="preview-static")
