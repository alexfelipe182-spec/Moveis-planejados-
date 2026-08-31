import secrets

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models import Organization, Subscription, User
from app.services.billing import subscription_allows_access

CSRF_COOKIE = "csrf_token"


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
    organization = db.get(Organization, user.organization_id)
    if not organization or organization.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Marcenaria suspensa ou indisponível")
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
    # CSRF é necessário quando a autenticação está sendo feita por cookie.
    # Clientes que usam Authorization: Bearer não precisam enviar o token CSRF.
    if access_token:
        _validate_csrf(csrf_cookie, csrf_header)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao administrador")
    return current_user


def require_workspace_admin(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    """Allow operational writes only while the tenant subscription grants access."""
    subscription = db.scalar(
        select(Subscription).where(Subscription.organization_id == current_user.organization_id)
    )
    if not subscription_allows_access(subscription):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="A assinatura da marcenaria não permite novas alterações",
        )
    return current_user


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito à plataforma")
    return current_user
