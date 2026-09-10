"""ASGI server for the existing Multi-Marcenarias frontend service."""

from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from starlette.routing import Route


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
INDEX = FRONTEND / "index.html"
AUTH_REFERENCE_STYLE = '<link rel="stylesheet" href="/authenticated-reference.css">'
AUTH_REFERENCE_SCRIPT = '<script src="/authenticated-reference.js"></script>'
DASHBOARD_GUARD_SCRIPT = '<script src="/dashboard-route-guard.js"></script>'
PRIVATE_ROOTS = {".git", "backend", "scripts", "tests"}
PRIVATE_SUFFIXES = {".cjs", ".py", ".pyc"}


def _safe_target(path: str) -> Path | None:
    parts = tuple(part for part in path.split("/") if part)
    if any(part in {".", ".."} or part.startswith(".") for part in parts):
        return None
    if parts and parts[0].lower() in PRIVATE_ROOTS:
        return None
    target = (FRONTEND / Path(*parts)).resolve()
    try:
        target.relative_to(FRONTEND.resolve())
    except ValueError:
        return None
    if target.suffix.lower() in PRIVATE_SUFFIXES:
        return None
    return target


def _index_response(path: str) -> Response:
    html = INDEX.read_text(encoding="utf-8")
    if AUTH_REFERENCE_STYLE not in html:
        html = html.replace("</head>", f"  {AUTH_REFERENCE_STYLE}\n</head>")
    if AUTH_REFERENCE_SCRIPT not in html:
        html = html.replace("</body>", f"  {AUTH_REFERENCE_SCRIPT}\n</body>")

    normalized = path.strip("/")
    if normalized == "dashboard" or normalized.startswith("dashboard/"):
        if DASHBOARD_GUARD_SCRIPT not in html:
            html = html.replace("</body>", f"  {DASHBOARD_GUARD_SCRIPT}\n</body>")
    return HTMLResponse(html)


async def health(_: Request) -> Response:
    return PlainTextResponse("ok")


async def frontend(request: Request) -> Response:
    path = request.path_params.get("path", "")
    target = _safe_target(path)
    if target is None:
        raise HTTPException(status_code=404)
    if target.is_file():
        return FileResponse(target)
    if path.startswith(("api/", "assets/")) or target.suffix:
        raise HTTPException(status_code=404)
    return _index_response(path)


async def frontend_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path == "/" or response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET", "HEAD"]),
        Route("/{path:path}", frontend, methods=["GET", "HEAD"]),
    ]
)
app.add_middleware(BaseHTTPMiddleware, dispatch=frontend_headers)