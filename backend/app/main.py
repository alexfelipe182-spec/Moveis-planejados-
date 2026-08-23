from fastapi import Cookie, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.auth import router as auth_router
from app.api.routes import api_router
from app.core.config import settings
from app.database import engine


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


app = FastAPI(title=settings.app_name, version="0.1.0", docs_url=None)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_router)


@app.get("/docs", include_in_schema=False)
def swagger_docs():
    """Swagger UI com teste de autenticação compatível com dispositivos móveis."""
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
        .ideal-auth-test input { box-sizing: border-box; width: 100%; max-width: 420px; padding: 11px; margin: 4px 0; }
        .ideal-auth-test button { padding: 11px 14px; margin: 4px 4px 4px 0; border: 1px solid #888; border-radius: 6px; background: white; }
        #ideal-auth-result { margin-top: 10px; white-space: pre-wrap; overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
      </style>
    </head>
    <body>
      <section class="ideal-auth-test" aria-label="Teste de autenticação">
        <strong>Teste de autenticação: Login → Refresh</strong>
        <div><input id="ideal-user" type="email" autocomplete="username" placeholder="E-mail"></div>
        <div><input id="ideal-pass" type="password" autocomplete="current-password" placeholder="Senha"></div>
        <div>
          <button id="ideal-login-refresh" type="button">Testar Login + Refresh</button>
          <button id="ideal-diagnose" type="button">Diagnosticar cookies</button>
        </div>
        <div id="ideal-auth-result" role="status">Aguardando teste...</div>
      </section>
      <div id="swagger-ui"></div>
      <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
      <script>
        (function () {
          const CSRF_KEY = "ideal_marcenaria_csrf";
          const result = document.getElementById("ideal-auth-result");
          const userInput = document.getElementById("ideal-user");
          const passInput = document.getElementById("ideal-pass");

          function setResult(text) { result.textContent = text; }
          function csrfFromCookie() {
            const prefix = "csrf_token=";
            const row = document.cookie.split("; ").find(function (item) { return item.indexOf(prefix) === 0; });
            return row ? decodeURIComponent(row.substring(prefix.length)) : null;
          }
          function csrfToken() { return csrfFromCookie() || localStorage.getItem(CSRF_KEY); }
          async function json(response) {
            const text = await response.text();
            try { return text ? JSON.parse(text) : {}; } catch (_) { return {}; }
          }

          document.getElementById("ideal-diagnose").addEventListener("click", async function () {
            setResult("Verificando cookies...");
            try {
              const token = csrfToken();
              const headers = { "Accept": "application/json" };
              if (token) headers["X-CSRF-Token"] = token;
              const response = await fetch("/api/v1/auth/cookie-diagnostic", {
                method: "GET", credentials: "include", cache: "no-store", headers: headers
              });
              setResult(JSON.stringify(await json(response), null, 2));
            } catch (error) { setResult("Erro de rede: " + error.message); }
          });

          document.getElementById("ideal-login-refresh").addEventListener("click", async function () {
            const username = userInput.value.trim();
            const password = passInput.value;
            if (!username || !password) { setResult("Informe e-mail e senha."); return; }
            setResult("Executando login...");
            try {
              const login = await fetch("/api/v1/auth/login", {
                method: "POST", credentials: "include", cache: "no-store",
                headers: { "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded" },
                body: new URLSearchParams({ grant_type: "", username: username, password: password, scope: "", client_id: "", client_secret: "" })
              });
              const loginBody = await json(login);
              if (!login.ok) { setResult("Login: " + login.status); return; }
              if (loginBody.csrf_token) localStorage.setItem(CSRF_KEY, loginBody.csrf_token);
              const token = csrfToken();
              if (!token) { setResult("Login: 200\nCSRF não encontrado."); return; }
              setResult("Login: 200\nExecutando refresh...");
              const refresh = await fetch("/api/v1/auth/refresh", {
                method: "POST", credentials: "include", cache: "no-store",
                headers: { "Accept": "application/json", "X-CSRF-Token": token }
              });
              const refreshBody = await json(refresh);
              if (!refresh.ok) {
                setResult("Login: 200\nRefresh: " + refresh.status + "\nErro: " + (refreshBody.detail || "falha"));
                return;
              }
              if (refreshBody.csrf_token) localStorage.setItem(CSRF_KEY, refreshBody.csrf_token);
              setResult("Login: 200\nRefresh: 200\nFluxo login → refresh funcionando.");
            } catch (error) { setResult("Erro de rede: " + error.message); }
          });

          window.ui = SwaggerUIBundle({
            url: "/openapi.json",
            dom_id: "#swagger-ui",
            deepLinking: true,
            requestInterceptor: function (request) {
              request.credentials = "include";
              const token = csrfToken();
              if (token && request.url.indexOf("/api/v1/auth/") !== -1) {
                request.headers = request.headers || {};
                request.headers["X-CSRF-Token"] = token;
              }
              return request;
            },
            responseInterceptor: function (response) {
              try {
                const body = response && (response.data || response.body);
                const parsed = typeof body === "string" ? JSON.parse(body) : body;
                if (parsed && parsed.csrf_token) localStorage.setItem(CSRF_KEY, parsed.csrf_token);
              } catch (_) {}
              return response;
            },
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
            layout: "BaseLayout"
          });
        })();
      </script>
    </body>
    </html>
    """
    response = HTMLResponse(html)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/api/v1/auth/cookie-diagnostic", tags=["authentication-diagnostics"])
def cookie_diagnostic(
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    csrf_token: str | None = Cookie(default=None),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    """Diagnóstico seguro: retorna apenas presença/comparação, nunca tokens."""
    return {
        "has_refresh_token": bool(refresh_token),
        "has_csrf_cookie": bool(csrf_token),
        "csrf_header_received": bool(csrf_header),
        "csrf_matches": bool(csrf_token and csrf_header and csrf_token == csrf_header),
        "origin": request.headers.get("origin"),
    }


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready", tags=["system"])
def readiness_check():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "service": settings.app_name}


@app.get("/", tags=["system"])
def root():
    return {"message": "API de Moveis Planejados funcionando"}
