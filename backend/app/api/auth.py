import hashlib
import re
import secrets
import smtplib
import unicodedata
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CSRF_COOKIE, require_csrf
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.models import Activity, PasswordResetToken, RefreshToken, Subscription, Tenant, User
from app.schemas.password_reset import PasswordResetConfirm, PasswordResetRequest, PasswordResetResponse
from app.schemas.tenant import BusinessRegister, BusinessRegisterResponse
from app.schemas.user import UserCreate, UserRead
from app.services.plans import TRIAL_DAYS

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _slug_base(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return (slug or "marcenaria")[:150]


def _available_tenant_slug(db: Session, business_name: str) -> str:
    base = _slug_base(business_name)
    candidate = base
    suffix = 2
    while db.scalar(select(Tenant.id).where(Tenant.slug == candidate)):
        candidate = f"{base[:140]}-{suffix}"
        suffix += 1
    return candidate


def _cookies(response: Response, access: str, refresh: str) -> str:
    secure = settings.environment == "production"
    samesite = "none" if secure else "lax"
    csrf = secrets.token_urlsafe(32)
    response.set_cookie("access_token", access, httponly=True, secure=secure, samesite=samesite, max_age=settings.access_token_expire_minutes * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=secure, samesite=samesite, max_age=settings.refresh_token_expire_days * 86400, path="/api/v1/auth")
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite=samesite, max_age=settings.refresh_token_expire_days * 86400, path="/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return csrf


def _send_reset_email(user: User, token: str) -> bool:
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, settings.smtp_from]):
        return False
    msg = EmailMessage()
    msg["Subject"] = "Recuperação de acesso — Multi-Marcenarias"
    msg["From"] = settings.smtp_from
    msg["To"] = user.email
    link = f"{settings.frontend_url}/#reset_token={token}"
    msg.set_content(f"Olá, {user.name}.\n\nUse este link para redefinir sua senha:\n{link}\n\nO link expira em {settings.password_reset_expire_minutes} minutos.\nSe você não solicitou a alteração, ignore este e-mail.")
    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    return True


@router.get("/csrf")
def get_csrf_token(response: Response, csrf_token: str | None = Cookie(default=None, alias=CSRF_COOKIE)):
    """Disponibiliza o token CSRF para clientes que usam autenticação por cookie."""
    secure = settings.environment == "production"
    samesite = "none" if secure else "lax"
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            CSRF_COOKIE,
            csrf_token,
            httponly=False,
            secure=secure,
            samesite=samesite,
            max_age=settings.refresh_token_expire_days * 86400,
            path="/",
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {"csrf_token": csrf_token}


@router.post(
    "/register-business",
    response_model=BusinessRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_business(payload: BusinessRegister, db: Session = Depends(get_db)):
    """Cria uma nova marcenaria, o primeiro administrador e seu teste grátis de 30 dias."""
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    tenant = Tenant(
        name=payload.business_name.strip(),
        slug=_available_tenant_slug(db, payload.business_name),
        plan_code=payload.plan_code,
    )
    owner = User(
        tenant=tenant,
        name=payload.owner_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        is_admin=True,
    )
    db.add_all([tenant, owner])
    try:
        db.flush()
        db.add(
            Subscription(
                tenant_id=tenant.id,
                provider="manual",
                plan_code=payload.plan_code,
                status="trialing",
                trial_end=_now() + timedelta(days=TRIAL_DAYS),
            )
        )
        db.add(
            Activity(
                user_id=owner.id,
                action="business_registered",
                entity="tenant",
                entity_id=tenant.id,
                description=f"Criou a marcenaria {tenant.name} com {TRIAL_DAYS} dias grátis",
            )
        )
        db.commit()
        db.refresh(tenant)
        db.refresh(owner)
    except Exception:
        db.rollback()
        raise
    return BusinessRegisterResponse(tenant=tenant, owner=owner)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Cadastro legado; novos clientes devem preferir /register-business."""
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        is_admin=False,
    )
    db.add(user)
    try:
        # The tenant-scoping hook creates and links a tenant for legacy users.
        # Once flushed, grant that tenant the same commercial trial as the
        # current business registration flow so no new account is born locked.
        db.flush()
        if not user.tenant_id:
            raise RuntimeError("Cadastro criado sem marcenaria vinculada")
        db.add(
            Subscription(
                tenant_id=user.tenant_id,
                provider="manual",
                plan_code="starter",
                status="trialing",
                trial_end=_now() + timedelta(days=TRIAL_DAYS),
            )
        )
        db.add(Activity(user_id=user.id, action="created", entity="user", entity_id=user.id, description=f"Cadastro de usuário {user.email} com {TRIAL_DAYS} dias grátis"))
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise
    return user


@router.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if not user.tenant_id:
        raise HTTPException(status_code=403, detail="Usuário sem marcenaria vinculada")
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Marcenaria indisponível")
    access = create_access_token(str(user.id))
    refresh, jti, expires = create_refresh_token(str(user.id))
    db.add(RefreshToken(user_id=user.id, token_jti=jti, expires_at=expires.replace(tzinfo=None)))
    db.add(Activity(user_id=user.id, action="login", entity="user", entity_id=user.id, description=f"Login realizado por {user.email}"))
    db.commit()
    csrf = _cookies(response, access, refresh)
    return {"access_token": access, "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60, "csrf_token": csrf}


@router.post("/password-reset/request", response_model=PasswordResetResponse, response_model_exclude_none=True)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if not user:
        return PasswordResetResponse(message="Se o e-mail estiver cadastrado, as instruções de recuperação serão enviadas.")
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).update({"used_at": _now()})
    token = secrets.token_urlsafe(48)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=_now() + timedelta(minutes=settings.password_reset_expire_minutes)))
    db.add(Activity(user_id=user.id, action="password_reset_requested", entity="user", entity_id=user.id, description="Solicitou recuperação de senha"))
    db.commit()
    try:
        sent = _send_reset_email(user, token)
    except (OSError, smtplib.SMTPException):
        sent = False
    debug = token if settings.environment != "production" and not sent else None
    return PasswordResetResponse(message="Se o e-mail estiver cadastrado, as instruções de recuperação serão enviadas.", debug_token=debug)


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    if not record or record.used_at is not None or record.expires_at <= _now():
        raise HTTPException(status_code=400, detail="Token inválido, expirado ou já utilizado")
    user = db.get(User, record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Usuário inválido ou inativo")
    user.password_hash = hash_password(payload.new_password)
    record.used_at = _now()
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked.is_(False),
    ).update({"revoked": True}, synchronize_session=False)
    db.add(Activity(user_id=user.id, action="password_reset", entity="user", entity_id=user.id, description="Senha redefinida com sucesso e sessões renováveis revogadas"))
    db.commit()
    return {"message": "Senha redefinida com sucesso. Faça login novamente."}


@router.post("/refresh")
def refresh(response: Response, _: None = Depends(require_csrf), refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token ausente")
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Refresh token inválido ou expirado") from None
    if payload.get("type") != "refresh" or not payload.get("sub") or not payload.get("jti"):
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    stored = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_jti == payload["jti"])
        .with_for_update()
    )
    if not stored or stored.revoked or stored.expires_at <= _now():
        raise HTTPException(status_code=401, detail="Refresh token revogado ou expirado")
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Usuário inválido") from None
    if stored.user_id != user_id:
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    user = db.get(User, user_id)
    if not user or not user.is_active or not user.tenant_id:
        raise HTTPException(status_code=401, detail="Usuário inválido")
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Marcenaria indisponível")
    stored.revoked = True
    access = create_access_token(str(user.id))
    new_refresh, jti, expires = create_refresh_token(str(user.id))
    db.add(RefreshToken(user_id=user.id, token_jti=jti, expires_at=expires.replace(tzinfo=None)))
    db.commit()
    csrf = _cookies(response, access, new_refresh)
    return {"access_token": access, "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60, "csrf_token": csrf}


@router.post("/logout", status_code=204)
def logout(response: Response, _: None = Depends(require_csrf), db: Session = Depends(get_db), refresh_token: str | None = Cookie(default=None)):
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            stored = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == payload.get("jti")))
            if stored:
                stored.revoked = True
                db.commit()
        except ValueError:
            pass
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
