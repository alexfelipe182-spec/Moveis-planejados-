import logging
import re
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Cookie, FastAPI, Header, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.auth import router as auth_router
from app.api.routes import api_router
from app.core.config import settings
from app.core.resilience import DistributedRateLimiter
from app.database import engine


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

rate_limiter = DistributedRateLimiter(
    settings.redis_url,
    limit=settings.rate_limit_per_minute,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        await rate_limiter.close()
        engine.dispose()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.environment == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        if response.status_code >= 500:
            log_method = logger.warning
        elif request.url.path in {"/health", "/ready"}:
            log_method = logger.debug
        else:
            log_method = logger.info
        log_method(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class TrafficProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: DistributedRateLimiter):
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in {"/health", "/ready"}:
            return await call_next(request)
        forwarded = request.headers.get("x-forwarded-for")
        client = forwarded.split(",", 1)[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        decision = await self.limiter.allow(client)
        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Muitas requisições. Tente novamente em instantes."},
                headers={"Retry-After": str(decision.retry_after)},
            )
        response = await call_next(request)
        response.headers.setdefault("X-RateLimit-Limit", str(settings.rate_limit_per_minute))
        return response


app = FastAPI(title=settings.app_name, version="0.1.0", docs_url=None, lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(
    TrafficProtectionMiddleware,
    limiter=rate_limiter,
)
app.add_middleware(ObservabilityMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_router)


@app.get("/docs", include_in_schema=False)
def swagger_docs():
    """Swagger UI com fluxo de autenticação compatível com dispositivos móveis."""
    if settings.environment == "production":
        response = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger",
            swagger_ui_parameters={"tryItOutEnabled": False},
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    html = """
    <!doctype html>
    <html lang="pt-BR">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
      <title>Moveis Planejados API - Swagger</title>
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
      <style>
        body { margin: 0; }
        .ideal-auth-test { margin: 12px auto; padding: 16px; max-width: 1180px; border: 1px solid #d0d0d0; border-radius: 10px; background: #fafafa; box-sizing: border-box; }
        .ideal-auth-test input { box-sizing: border-box; width: 100%; max-width: 420px; min-height: 44px; padding: 11px; margin: 4px 0; font-size: 16px; }
        .ideal-auth-test button { min-height: 44px; padding: 11px 14px; margin: 4px 4px 4px 0; border: 1px solid #888; border-radius: 6px; background: white; font-size: 16px; touch-action: manipulation; }
        .ideal-auth-test button:disabled { opacity: .55; }
        #ideal-auth-result { margin-top: 10px; white-space: pre-wrap; overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
      </style>
    </head>
    <body>
      <section class="ideal-auth-test" aria-label="Teste de autenticação">
        <strong>Teste de autenticação: Login → Refresh</strong>
        <div><input id="ideal-user" type="email" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="E-mail"></div>
        <div><input id="ideal-pass" type="password" autocomplete="current-password" placeholder="Senha"></div>
        <div>
          <button id="ideal-login-refresh" type="button">Testar Login + Refresh</button>
          <button id="ideal-diagnose" type="button">Diagnosticar cookies</button>
        </div>
        <div id="ideal-auth-result" role="status" aria-live="polite">Aguardando teste...</div>
      </section>
      <div id="swagger-ui"></div>
      <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
      <script>
        (function () {
          "use strict";
          var csrfMemory = null;
          var result = document.getElementById("ideal-auth-result");
          var userInput = document.getElementById("ideal-user");
          var passInput = document.getElementById("ideal-pass");
          var loginButton = document.getElementById("ideal-login-refresh");
          var diagnoseButton = document.getElementById("ideal-diagnose");
          function setResult(text) { if (result) result.textContent = text; }
          function csrfFromCookie() {
            var prefix = "csrf_token=";
            var cookies = document.cookie ? document.cookie.split("; ") : [];
            for (var i = 0; i < cookies.length; i += 1) {
              if (cookies[i].indexOf(prefix) === 0) return decodeURIComponent(cookies[i].substring(prefix.length));
            }
            return null;
          }
          function csrfToken() { return csrfFromCookie() || csrfMemory; }
          async function readJson(response) { var text = await response.text(); try { return text ? JSON.parse(text) : {}; } catch (_) { return {}; } }
          function csrfHeaders() { var token = csrfToken(); var headers = { "Accept": "application/json" }; if (token) headers["X-CSRF-Token"] = token; return headers; }
          if (diagnoseButton) diagnoseButton.addEventListener("click", async function () {
            diagnoseButton.disabled = true; setResult("Verificando cookies...");
            try { var response = await fetch("/api/v1/auth/cookie-diagnostic", { method: "GET", credentials: "include", cache: "no-store", headers: csrfHeaders() }); setResult(JSON.stringify(await readJson(response), null, 2)); }
            catch (error) { setResult("Erro de rede: " + (error && error.message ? error.message : "desconhecido")); }
            finally { diagnoseButton.disabled = false; }
          });
          if (loginButton) loginButton.addEventListener("click", async function () {
            var username = userInput ? userInput.value.trim() : ""; var password = passInput ? passInput.value : "";
            if (!username || !password) { setResult("Informe e-mail e senha."); return; }
            loginButton.disabled = true; if (diagnoseButton) diagnoseButton.disabled = true; setResult("Executando login...");
            try {
              var login = await fetch("/api/v1/auth/login", { method: "POST", credentials: "include", cache: "no-store", headers: { "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" }, body: new URLSearchParams({ grant_type: "", username: username, password: password, scope: "", client_id: "", client_secret: "" }).toString() });
              var loginBody = await readJson(login);
              if (!login.ok) { setResult("Login: " + login.status + "\nErro: " + (loginBody.detail || "falha")); return; }
              csrfMemory = loginBody.csrf_token || csrfFromCookie();
              if (!csrfToken()) { setResult("Login: 200\nCSRF não encontrado no cookie nem na resposta."); return; }
              var diagnostic = await fetch("/api/v1/auth/cookie-diagnostic", { method: "GET", credentials: "include", cache: "no-store", headers: csrfHeaders() });
              var diagnosticBody = await readJson(diagnostic);
              if (!diagnostic.ok || !diagnosticBody.csrf_matches || !diagnosticBody.has_refresh_token) { setResult("Login: 200\nDiagnóstico: falhou\n" + JSON.stringify(diagnosticBody, null, 2)); return; }
              setResult("Login: 200\nDiagnóstico: OK\nExecutando refresh...");
              var refresh = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include", cache: "no-store", headers: csrfHeaders() });
              var refreshBody = await readJson(refresh);
              if (!refresh.ok) { setResult("Login: 200\nDiagnóstico: OK\nRefresh: " + refresh.status + "\nErro: " + (refreshBody.detail || "falha")); return; }
              csrfMemory = refreshBody.csrf_token || csrfFromCookie(); setResult("Login: 200\nDiagnóstico: OK\nRefresh: 200\nRotação: OK\nFluxo login → refresh funcionando.");
            } catch (error) { setResult("Erro de rede: " + (error && error.message ? error.message : "desconhecido")); }
            finally { loginButton.disabled = false; if (diagnoseButton) diagnoseButton.disabled = false; }
          });
          if (typeof SwaggerUIBundle === "function") {
            window.ui = SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui", deepLinking: true, requestInterceptor: function (request) { request.credentials = "include"; var token = csrfToken(); if (token && request.url.indexOf("/api/v1/auth/") !== -1) { request.headers = request.headers || {}; request.headers["X-CSRF-Token"] = token; } return request; }, responseInterceptor: function (response) { try { var body = response && (response.data || response.body); var parsed = typeof body === "string" ? JSON.parse(body) : body; if (parsed && parsed.csrf_token) csrfMemory = parsed.csrf_token; } catch (_) {} return response; }, presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset], layout: "BaseLayout" });
          }
        })();
      </script>
    </body>
    </html>
    """
    response = HTMLResponse(html)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get(
    "/api/v1/auth/cookie-diagnostic",
    tags=["authentication-diagnostics"],
    include_in_schema=settings.environment != "production",
)
def cookie_diagnostic(request: Request, refresh_token: str | None = Cookie(default=None), csrf_token: str | None = Cookie(default=None), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
    """Diagnóstico seguro: retorna apenas presença/comparação, nunca tokens."""
    if settings.environment == "production":
        raise HTTPException(status_code=404, detail="Not Found")
    return {"has_refresh_token": bool(refresh_token), "has_csrf_cookie": bool(csrf_token), "csrf_header_received": bool(csrf_header), "csrf_matches": bool(csrf_token and csrf_header and csrf_token == csrf_header), "origin": request.headers.get("origin")}


@app.get("/health", tags=["system"])
def health_check(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready", tags=["system"])
async def readiness_check(response: Response):
    dependencies = {"postgres": "ok", "redis": "ok"}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness_failed dependency=postgres error_type=%s", type(exc).__name__)
        dependencies["postgres"] = "unhealthy"

    try:
        redis_ok = bool(await rate_limiter.redis.ping())
    except Exception as exc:
        logger.warning("readiness_failed dependency=redis error_type=%s", type(exc).__name__)
        redis_ok = False
    if not redis_ok:
        dependencies["redis"] = "unhealthy"

    if "unhealthy" in dependencies.values():
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "service": settings.app_name, "dependencies": dependencies},
            headers={"Cache-Control": "no-store"},
        )

    response.headers["Cache-Control"] = "no-store"
    return {"status": "ready", "service": settings.app_name, "dependencies": dependencies}


@app.get("/", tags=["system"])
def root():
    return {"message": "API de Moveis Planejados funcionando"}
