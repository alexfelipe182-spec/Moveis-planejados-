from fastapi import FastAPI, Cookie, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
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
    """Swagger UI com teste integrado do fluxo login -> refresh por cookies + CSRF."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
      <title>API Moveis Planejados - Swagger</title>
      <style>
        .ideal-auth-test { margin: 20px auto; padding: 16px; max-width: 1200px; border: 1px solid #ccc; border-radius: 8px; background: #fafafa; }
        .ideal-auth-test input { padding: 8px; margin: 4px; min-width: 220px; }
        .ideal-auth-test button { padding: 9px 14px; margin: 4px; cursor: pointer; }
        #ideal-auth-result { white-space: pre-wrap; margin-top: 10px; font-family: monospace; }
      </style>
    </head>
    <body>
      <div class="ideal-auth-test">
        <strong>Teste de autenticação: Login → Refresh</strong><br>
        <input id="ideal-user" type="email" placeholder="E-mail">
        <input id="ideal-pass" type="password" placeholder="Senha">
        <button id="ideal-test-auth" type="button">Testar Login + Refresh</button>
        <button id="ideal-cookie-diagnostic" type="button">Diagnosticar cookies</button>
        <div id="ideal-auth-result">Aguardando teste...</div>
      </div>
      <div id="swagger-ui"></div>
      <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
      <script>
        const CSRF_STORAGE_KEY = "ideal_marcenaria_csrf";

        function getCookie(name) {
          const prefix = name + "=";
          const item = document.cookie.split("; ").find(row => row.startsWith(prefix));
          return item ? decodeURIComponent(item.substring(prefix.length)) : null;
        }

        function getCsrfToken() {
          return getCookie("csrf_token") || localStorage.getItem(CSRF_STORAGE_KEY);
        }

        async function readJson(response) {
          const text = await response.text();
          try { return text ? JSON.parse(text) : {}; } catch (_) { return { raw: text }; }
        }

        async function testLoginRefresh() {
          const result = document.getElementById("ideal-auth-result");
          const username = document.getElementById("ideal-user").value.trim();
          const password = document.getElementById("ideal-pass").value;
          if (!username || !password) { result.textContent = "Informe e-mail e senha para o teste."; return; }
          result.textContent = "Executando login...";
          try {
            const loginResponse = await fetch("/api/v1/auth/login", {
              method: "POST", credentials: "include",
              headers: { "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json" },
              body: new URLSearchParams({ grant_type: "", username, password, scope: "", client_id: "", client_secret: "" })
            });
            const loginBody = await readJson(loginResponse);
            if (!loginResponse.ok) { result.textContent = `Login: ${loginResponse.status}`; return; }
            if (loginBody.csrf_token) localStorage.setItem(CSRF_STORAGE_KEY, loginBody.csrf_token);
            const csrf = loginBody.csrf_token || getCsrfToken();
            if (!csrf) { result.textContent = "Login: 200\nCSRF não recebido."; return; }
            result.textContent = "Login: 200\nExecutando refresh...";
            const refreshResponse = await fetch("/api/v1/auth/refresh", {
              method: "POST", credentials: "include",
              headers: { "Accept": "application/json", "X-CSRF-Token": csrf }
            });
            const refreshBody = await readJson(refreshResponse);
            if (refreshResponse.ok) {
              if (refreshBody.csrf_token) localStorage.setItem(CSRF_STORAGE_KEY, refreshBody.csrf_token);
              result.textContent = `Login: 200\nRefresh: ${refreshResponse.status}\nFluxo login → refresh funcionando.`;
            } else {
              result.textContent = `Login: 200\nRefresh: ${refreshResponse.status}\nErro: ${refreshBody.detail || "falha"}`;
            }
          } catch (error) { result.textContent = "Erro de rede: " + error.message; }
        }

        async function diagnoseCookies() {
          const result = document.getElementById("ideal-auth-result");
          result.textContent = "Verificando cookies (sem revelar valores)...";
          try {
            const csrf = getCookie("csrf_token");
            const response = await fetch("/api/v1/auth/cookie-diagnostic", {
              method: "GET", credentials: "include", cache: "no-store",
              headers: csrf ? { "X-CSRF-Token": csrf } : {}
            });
            const body = await readJson(response);
            result.textContent = JSON.stringify(body, null, 2);
          } catch (error) { result.textContent = "Erro de rede: " + error.message; }
        }

        document.getElementById("ideal-test-auth").addEventListener("click", testLoginRefresh);
        document.getElementById("ideal-cookie-diagnostic").addEventListener("click", diagnoseCookies);

        window.ui = SwaggerUIBundle({
          url: "/openapi.json", dom_id: "#swagger-ui", deepLinking: true,
          requestInterceptor: function(request) {
            request.credentials = "include";
            const csrf = getCsrfToken();
            if (csrf && request.url.includes("/api/v1/auth/")) {
              request.headers = request.headers || {};
              request.headers["X-CSRF-Token"] = csrf;
            }
            return request;
          },
          responseInterceptor: function(response) {
            try {
              const body = response && (response.data || response.body);
              const parsed = typeof body === "string" ? JSON.parse(body) : body;
              if (parsed && parsed.csrf_token) localStorage.setItem(CSRF_STORAGE_KEY, parsed.csrf_token);
            } catch (_) {}
            return response;
          },
          presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
          layout: "BaseLayout"
        });
      </script>
    </body>
    </html>
    """
    response = HTMLResponse(html)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/api/v1/auth/cookie-diagnostic", include_in_schema=False)
def cookie_diagnostic(
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    csrf_token: str | None = Cookie(default=None),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
):
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
    """Confirma que a aplicação e o banco estão prontos para receber tráfego."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "service": settings.app_name}


@app.get("/", tags=["system"])
def root():
    return {"message": "API de Moveis Planejados funcionando"}
