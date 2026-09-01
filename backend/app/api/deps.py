import secrets

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models import Tenant, User
from app.services.plans import ensure_commercial_access

CSRF_COOKIE = "csrf_token"
COMMERCIAL_ACCESS_EXEMPT_PATHS = {
    "/api/v1/billing/subscription",
    "/api/v1/billing/checkout",
    "/api/v1/billing/portal",
    "/api/v1/protected/me",
}


def _requires_commercial_access(path: str) -> bool:
    if path in COMMERCIAL_ACCESS_EXEMPT_PATHS:
        return False
    if path.startswith("/api/v1/platform/"):
        return False
    return True


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
) -> User:
    token = access_token
    if not token:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado") from None
    if payload.get("type") != "access" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso inválido")
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso inválido") from None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido ou inativo")
    if not user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário sem marcenaria vinculada")
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Marcenaria indisponível")
    db.info["tenant_id"] = user.tenant_id
    if _requires_commercial_access(request.url.path):
        ensure_commercial_access(db, tenant)
    return user


def _validate_csrf(csrf_cookie: str | None, csrf_header: str | None) -> None:
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token inválido")


def require_csrf(
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    _validate_csrf(csrf_cookie, csrf_header)


def require_cookie_csrf(
    access_token: str | None = Cookie(default=None),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    if access_token:
        _validate_csrf(csrf_cookie, csrf_header)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao administrador")
    return current_user
