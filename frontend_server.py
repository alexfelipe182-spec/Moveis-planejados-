"""ASGI server for the existing Multi-Marcenarias frontend service."""

from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import Route


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
INDEX = FRONTEND / "index.html"
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
    return FileResponse(INDEX)


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
