from fastapi import FastAPI
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


app = FastAPI(title=settings.app_name, version="0.1.0")
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
    """Swagger UI com cookies, CSRF e refresh token habilitados para testes."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
      <title>API Moveis Planejados - Swagger</title>
    </head>
    <body>
      <div id="swagger-ui"></div>
      <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
      <script>
        const CSRF_STORAGE_KEY = "ideal_marcenaria_csrf";
        const CSRF_PATH = "/api/v1/auth/csrf";

        function getCookie(name) {
          const prefix = name + "=";
          const item = document.cookie.split("; ").find(row => row.startsWith(prefix));
          return item ? decodeURIComponent(item.substring(prefix.length)) : null;
        }

        function getCsrfToken() {
          return getCookie("csrf_token") || localStorage.getItem(CSRF_STORAGE_KEY);
        }

        function saveCsrfFromResponse(response) {
          if (!response) return;
          let data = response.data ?? response.body ?? response.text;
          if (typeof data === "string") {
            try { data = JSON.parse(data); } catch (_) { return; }
          }
          if (data && data.csrf_token) {
            localStorage.setItem(CSRF_STORAGE_KEY, data.csrf_token);
          }
        }

        async function ensureCsrfCookie() {
          if (getCookie("csrf_token")) return getCookie("csrf_token");
          try {
            const response = await fetch(CSRF_PATH, {
              method: "GET",
              credentials: "include",
              cache: "no-store",
              headers: { "Accept": "application/json" }
            });
            if (response.ok) {
              const data = await response.json();
              if (data && data.csrf_token) {
                localStorage.setItem(CSRF_STORAGE_KEY, data.csrf_token);
              }
            }
          } catch (_) {}
          return getCsrfToken();
        }

        async function csrfRequestInterceptor(request) {
          request.credentials = "include";

          const isAuth = request.url.includes("/api/v1/auth/");
          const isRefresh = request.url.includes("/api/v1/auth/refresh");

          if (isRefresh) {
            await ensureCsrfCookie();
          }

          const csrf = getCsrfToken();
          if (csrf && isAuth) {
            request.headers = request.headers || {};
            request.headers["X-CSRF-Token"] = csrf;
          }

          return request;
        }

        function csrfResponseInterceptor(response) {
          saveCsrfFromResponse(response);
          return response;
        }

        window.ui = SwaggerUIBundle({
          url: "/openapi.json",
          dom_id: "#swagger-ui",
          deepLinking: true,
          requestInterceptor: csrfRequestInterceptor,
          responseInterceptor: csrfResponseInterceptor,
          presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.SwaggerUIStandalonePreset
          ],
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
