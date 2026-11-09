import hashlib
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_cookie_csrf
from app.core.config import settings
from app.core.security import create_customer_access_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.models import (
    Activity,
    Customer,
    CustomerPortalAccount,
    CustomerPortalMessage,
    Project,
    Quote,
    Tenant,
    User,
)
from app.models.tenant import utc_now_naive
from app.schemas.customer_portal import (
    CustomerPortalActivate,
    CustomerPortalAdminMessage,
    CustomerPortalDecision,
    CustomerPortalLogin,
    CustomerPortalMessageCreate,
    CustomerPortalMessageRead,
    CustomerPortalProjectRead,
    CustomerPortalQuoteRead,
    CustomerPortalResetConfirm,
    CustomerPortalResetRequest,
)
from app.services.automation import enqueue, process_job
from app.services.plans import ensure_capacity


router = APIRouter(prefix="/customer-portal", tags=["Customer Portal"])
CUSTOMER_ACCESS_COOKIE = "customer_access_token"
CUSTOMER_CSRF_COOKIE = "customer_csrf_token"
VISIBLE_QUOTE_STATUSES = {"sent", "accepted", "declined", "completed"}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _cookie_options() -> dict:
    secure = settings.environment == "production"
    return {"secure": secure, "samesite": "none" if secure else "lax", "path": "/"}


def _set_customer_session(response: Response, account: CustomerPortalAccount) -> tuple[str, str]:
    csrf_token = secrets.token_urlsafe(32)
    access_token = create_customer_access_token(str(account.id))
    max_age = settings.customer_portal_session_minutes * 60
    options = _cookie_options()
    response.set_cookie(
        CUSTOMER_ACCESS_COOKIE,
        access_token,
        httponly=True,
        max_age=max_age,
        **options,
    )
    response.set_cookie(
        CUSTOMER_CSRF_COOKIE,
        csrf_token,
        httponly=False,
        max_age=max_age,
        **options,
    )
    response.headers["Cache-Control"] = "no-store"
    return csrf_token, access_token


def _clear_customer_session(response: Response) -> None:
    options = _cookie_options()
    response.delete_cookie(CUSTOMER_ACCESS_COOKIE, httponly=True, **options)
    response.delete_cookie(CUSTOMER_CSRF_COOKIE, httponly=False, **options)
    response.headers["Cache-Control"] = "no-store"


def _send_portal_email(to: str, subject: str, body: str) -> bool:
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, settings.smtp_from]):
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(body)
    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
    return True


def _portal_account_unscoped(db: Session, account_id: int) -> CustomerPortalAccount | None:
    return db.scalar(
        select(CustomerPortalAccount)
        .where(CustomerPortalAccount.id == account_id)
        .execution_options(skip_tenant_scope=True)
    )


def get_current_customer(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=CUSTOMER_ACCESS_COOKIE),
) -> CustomerPortalAccount:
    if not token:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Acesso do cliente necessário")
    try:
        payload = decode_token(token)
        if payload.get("type") != "customer_access":
            raise ValueError
        account_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Sessão do cliente inválida ou expirada") from None

    account = _portal_account_unscoped(db, account_id)
    if not account or not account.is_active or not account.password_hash:
        raise HTTPException(status_code=401, detail="Conta do cliente inválida ou inativa")
    tenant = db.get(Tenant, account.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Marcenaria indisponível")
    db.info["tenant_id"] = account.tenant_id
    request.state.tenant_id = account.tenant_id
    customer = db.get(Customer, account.customer_id)
    if customer is None:
        raise HTTPException(status_code=401, detail="Cliente não encontrado")
    return account


def require_customer_csrf(
    request: Request,
    access_token: str | None = Cookie(default=None, alias=CUSTOMER_ACCESS_COOKIE),
    csrf_cookie: str | None = Cookie(default=None, alias=CUSTOMER_CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    if not access_token and request.headers.get("Authorization", "").startswith("Bearer "):
        return
    if not access_token or not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF do portal do cliente inválido")


def _validate_linked_records(
    db: Session,
    customer_id: int,
    quote_id: int | None,
    project_id: int | None,
) -> None:
    if quote_id is not None:
        quote = db.scalar(select(Quote).where(Quote.id == quote_id, Quote.customer_id == customer_id))
        if quote is None:
            raise HTTPException(status_code=404, detail="Orçamento não encontrado para este cliente")
    if project_id is not None:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.customer_id == customer_id))
        if project is None:
            raise HTTPException(status_code=404, detail="Projeto não encontrado para este cliente")


@router.post("/login")
def customer_login(payload: CustomerPortalLogin, response: Response, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.slug == payload.business_slug.strip().lower()))
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=401, detail="Marcenaria, e-mail ou senha inválidos")
    account = db.scalar(
        select(CustomerPortalAccount)
        .where(
            CustomerPortalAccount.tenant_id == tenant.id,
            CustomerPortalAccount.email == str(payload.email).strip().lower(),
        )
        .execution_options(skip_tenant_scope=True)
    )
    if not account or not account.is_active or not account.password_hash or not verify_password(payload.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Marcenaria, e-mail ou senha inválidos")
    db.info["tenant_id"] = tenant.id
    customer = db.get(Customer, account.customer_id)
    if customer is None:
        raise HTTPException(status_code=401, detail="Conta do cliente inválida")
    account.last_login_at = utc_now_naive()
    db.commit()
    csrf_token, access_token = _set_customer_session(response, account)
    return {
        "csrf_token": csrf_token,
        "access_token": access_token,
        "customer": {"id": customer.id, "name": customer.name, "email": customer.email},
        "tenant": {"name": tenant.name, "slug": tenant.slug},
    }


@router.post("/activate")
def activate_customer_portal(payload: CustomerPortalActivate, response: Response, db: Session = Depends(get_db)):
    account = db.scalar(
        select(CustomerPortalAccount)
        .where(CustomerPortalAccount.invitation_token_hash == _token_hash(payload.token))
        .execution_options(skip_tenant_scope=True)
    )
    if not account or not account.invitation_expires_at or account.invitation_expires_at < utc_now_naive():
        raise HTTPException(status_code=400, detail="Convite inválido ou expirado")
    tenant = db.get(Tenant, account.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Marcenaria indisponível")
    db.info["tenant_id"] = account.tenant_id
    account.password_hash = hash_password(payload.password)
    account.invitation_token_hash = None
    account.invitation_expires_at = None
    account.is_active = True
    account.last_login_at = utc_now_naive()
    customer = db.get(Customer, account.customer_id)
    db.add(Activity(user_id=None, action="portal_activated", entity="customer", entity_id=account.customer_id,
                    description=f"Cliente {customer.name} ativou o portal"))
    db.commit()
    csrf_token, access_token = _set_customer_session(response, account)
    return {
        "csrf_token": csrf_token,
        "access_token": access_token,
        "customer": {"id": customer.id, "name": customer.name, "email": customer.email},
        "tenant": {"name": tenant.name, "slug": tenant.slug},
    }


@router.post("/logout", status_code=204, dependencies=[Depends(require_customer_csrf)])
def customer_logout(response: Response):
    _clear_customer_session(response)


@router.get("/me")
def customer_me(account: CustomerPortalAccount = Depends(get_current_customer), db: Session = Depends(get_db)):
    customer = db.get(Customer, account.customer_id)
    tenant = db.get(Tenant, account.tenant_id)
    return {
        "customer": {"id": customer.id, "name": customer.name, "email": customer.email,
                     "phone": customer.phone, "address": customer.address},
        "tenant": {"name": tenant.name, "slug": tenant.slug},
    }


@router.get("/quotes", response_model=list[CustomerPortalQuoteRead])
def customer_quotes(account: CustomerPortalAccount = Depends(get_current_customer), db: Session = Depends(get_db)):
    return list(db.scalars(
        select(Quote)
        .where(Quote.customer_id == account.customer_id, Quote.status.in_(VISIBLE_QUOTE_STATUSES))
        .order_by(Quote.created_at.desc())
    ))


@router.get("/quotes/{quote_id}", response_model=CustomerPortalQuoteRead)
def customer_quote(quote_id: int, account: CustomerPortalAccount = Depends(get_current_customer), db: Session = Depends(get_db)):
    quote = db.scalar(select(Quote).where(
        Quote.id == quote_id,
        Quote.customer_id == account.customer_id,
        Quote.status.in_(VISIBLE_QUOTE_STATUSES),
    ))
    if quote is None:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return quote


@router.patch(
    "/quotes/{quote_id}/decision",
    response_model=CustomerPortalQuoteRead,
    dependencies=[Depends(require_customer_csrf)],
)
def customer_quote_decision(
    quote_id: int,
    payload: CustomerPortalDecision,
    account: CustomerPortalAccount = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    quote = db.scalar(select(Quote).where(
        Quote.id == quote_id, Quote.customer_id == account.customer_id
    ).with_for_update())
    if quote is None:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if quote.status != "sent":
        raise HTTPException(status_code=409, detail="Esta proposta não está aguardando uma decisão")
    tenant = db.get(Tenant, account.tenant_id)
    if payload.status == "accepted" and db.scalar(select(Project).where(Project.quote_id == quote.id)) is None:
        ensure_capacity(db, tenant, "projects")
    quote.status = payload.status
    customer = db.get(Customer, account.customer_id)
    label = "aceitou" if payload.status == "accepted" else "recusou"
    activity = Activity(user_id=None, action=payload.status, entity="quote", entity_id=quote.id,
                        description=f"Cliente {customer.name} {label} a proposta #{quote.id} pelo portal")
    db.add(activity)
    db.flush()
    event_type = "quote.accepted" if payload.status == "accepted" else "quote.declined"
    job = enqueue(
        db,
        tenant_id=account.tenant_id,
        event_type=event_type,
        payload={"entity_id": quote.id, "activity_id": activity.id},
        idempotency_key=f"customer-portal:{event_type}:{activity.id}",
    )
    process_job(db, job)
    db.commit()
    db.refresh(quote)
    return quote


@router.get("/projects", response_model=list[CustomerPortalProjectRead])
def customer_projects(account: CustomerPortalAccount = Depends(get_current_customer), db: Session = Depends(get_db)):
    return list(db.scalars(
        select(Project).where(Project.customer_id == account.customer_id).order_by(Project.updated_at.desc())
    ))


@router.get("/messages", response_model=list[CustomerPortalMessageRead])
def customer_messages(account: CustomerPortalAccount = Depends(get_current_customer), db: Session = Depends(get_db)):
    return list(db.scalars(
        select(CustomerPortalMessage)
        .where(CustomerPortalMessage.customer_id == account.customer_id)
        .order_by(CustomerPortalMessage.created_at.asc())
    ))


@router.post(
    "/messages",
    response_model=CustomerPortalMessageRead,
    status_code=201,
    dependencies=[Depends(require_customer_csrf)],
)
def create_customer_message(
    payload: CustomerPortalMessageCreate,
    account: CustomerPortalAccount = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _validate_linked_records(db, account.customer_id, payload.quote_id, payload.project_id)
    message = CustomerPortalMessage(
        customer_id=account.customer_id,
        quote_id=payload.quote_id,
        project_id=payload.project_id,
        author_type="customer",
        body=payload.body.strip(),
    )
    db.add(message)
    db.add(Activity(user_id=None, action="portal_message", entity="customer", entity_id=account.customer_id,
                    description="Cliente enviou uma mensagem pelo portal"))
    db.commit()
    db.refresh(message)
    return message


@router.post("/password-reset/request")
def request_customer_reset(payload: CustomerPortalResetRequest, db: Session = Depends(get_db)):
    generic = {"message": "Se a conta existir, as instruções serão enviadas ao e-mail informado."}
    tenant = db.scalar(select(Tenant).where(Tenant.slug == payload.business_slug.strip().lower()))
    if tenant is None:
        return generic
    account = db.scalar(
        select(CustomerPortalAccount)
        .where(CustomerPortalAccount.tenant_id == tenant.id,
               CustomerPortalAccount.email == str(payload.email).strip().lower())
        .execution_options(skip_tenant_scope=True)
    )
    if account is None or not account.is_active:
        return generic
    token = secrets.token_urlsafe(32)
    account.reset_token_hash = _token_hash(token)
    account.reset_expires_at = utc_now_naive() + timedelta(minutes=settings.password_reset_expire_minutes)
    db.commit()
    link = f"{settings.frontend_url}/?customer_portal_reset={token}&marcenaria={tenant.slug}#cliente"
    try:
        _send_portal_email(account.email, "Redefinição de senha — Portal do Cliente",
                           f"Use este link para criar uma nova senha:\n{link}\n\nO link expira em {settings.password_reset_expire_minutes} minutos.")
    except (OSError, smtplib.SMTPException):
        pass
    if settings.environment != "production":
        generic["debug_token"] = token
    return generic


@router.post("/password-reset/confirm")
def confirm_customer_reset(payload: CustomerPortalResetConfirm, db: Session = Depends(get_db)):
    account = db.scalar(
        select(CustomerPortalAccount)
        .where(CustomerPortalAccount.reset_token_hash == _token_hash(payload.token))
        .execution_options(skip_tenant_scope=True)
    )
    if not account or not account.reset_expires_at or account.reset_expires_at < utc_now_naive():
        raise HTTPException(status_code=400, detail="Link de recuperação inválido ou expirado")
    db.info["tenant_id"] = account.tenant_id
    account.password_hash = hash_password(payload.password)
    account.reset_token_hash = None
    account.reset_expires_at = None
    db.commit()
    return {"message": "Senha redefinida com sucesso."}


@router.get("/admin/customers/{customer_id}")
def portal_admin_status(
    customer_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    account = db.scalar(select(CustomerPortalAccount).where(CustomerPortalAccount.customer_id == customer_id))
    return {
        "enabled": account is not None and account.is_active,
        "activated": bool(account and account.password_hash),
        "email": account.email if account else customer.email,
        "last_login_at": account.last_login_at if account else None,
    }


@router.post(
    "/admin/customers/{customer_id}/invite",
    dependencies=[Depends(require_cookie_csrf)],
)
def portal_admin_invite(
    customer_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if not customer.email:
        raise HTTPException(status_code=409, detail="Cadastre o e-mail do cliente antes de gerar o acesso")
    tenant = db.get(Tenant, current_user.tenant_id)
    account = db.scalar(select(CustomerPortalAccount).where(CustomerPortalAccount.customer_id == customer_id))
    email = customer.email.strip().lower()
    if account is None:
        account = CustomerPortalAccount(customer_id=customer.id, email=email, is_active=True)
        db.add(account)
    else:
        account.email = email
        account.is_active = True
    token = secrets.token_urlsafe(32)
    account.invitation_token_hash = _token_hash(token)
    account.invitation_expires_at = utc_now_naive() + timedelta(hours=72)
    db.flush()
    invitation_url = f"{settings.frontend_url}/?customer_portal_token={token}&marcenaria={tenant.slug}#cliente"
    email_sent = False
    try:
        email_sent = _send_portal_email(
            account.email,
            f"Acesso ao portal — {tenant.name}",
            f"Olá, {customer.name}.\n\nA {tenant.name} liberou seu Portal do Cliente. Crie sua senha neste link:\n{invitation_url}\n\nO convite expira em 72 horas.",
        )
    except (OSError, smtplib.SMTPException):
        email_sent = False
    db.add(Activity(user_id=current_user.id, action="portal_invited", entity="customer", entity_id=customer.id,
                    description=f"Gerou acesso ao portal para {customer.name}"))
    db.commit()
    return {"invitation_url": invitation_url, "expires_in_hours": 72, "email_sent": email_sent}


@router.get("/admin/customers/{customer_id}/messages", response_model=list[CustomerPortalMessageRead])
def portal_admin_messages(
    customer_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return list(db.scalars(
        select(CustomerPortalMessage)
        .where(CustomerPortalMessage.customer_id == customer_id)
        .order_by(CustomerPortalMessage.created_at.asc())
    ))


@router.post(
    "/admin/customers/{customer_id}/messages",
    response_model=CustomerPortalMessageRead,
    status_code=201,
    dependencies=[Depends(require_cookie_csrf)],
)
def portal_admin_create_message(
    customer_id: int,
    payload: CustomerPortalAdminMessage,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    _validate_linked_records(db, customer_id, payload.quote_id, payload.project_id)
    message = CustomerPortalMessage(customer_id=customer_id, quote_id=payload.quote_id,
                                    project_id=payload.project_id, author_type="staff", body=payload.body.strip())
    db.add(message)
    db.add(Activity(user_id=current_user.id, action="portal_reply", entity="customer", entity_id=customer_id,
                    description="Marcenaria respondeu ao cliente pelo portal"))
    db.commit()
    db.refresh(message)
    return message
