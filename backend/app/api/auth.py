from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.models import RefreshToken, User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _cookies(response: Response, access: str, refresh: str) -> None:
    secure = settings.environment == "production"
    response.set_cookie("access_token", access, httponly=True, secure=secure, samesite="lax", max_age=settings.access_token_expire_minutes * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=secure, samesite="lax", max_age=settings.refresh_token_expire_days * 86400, path="/auth")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password), is_admin=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form_data.username))
    if not user or not user.is_active or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    access = create_access_token(str(user.id))
    refresh, jti, expires = create_refresh_token(str(user.id))
    db.add(RefreshToken(user_id=user.id, token_jti=jti, expires_at=expires.replace(tzinfo=None)))
    db.commit()
    _cookies(response, access, refresh)
    return {"access_token": access, "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60}


@router.post("/refresh")
def refresh(response: Response, refresh_token: str | None = None, db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(401, "Refresh token ausente")
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(401, "Refresh token inválido ou expirado")
    if payload.get("type") != "refresh" or not payload.get("sub") or not payload.get("jti"):
        raise HTTPException(401, "Refresh token inválido")
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == payload["jti"]))
    if not stored or stored.revoked or stored.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(401, "Refresh token revogado ou expirado")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "Usuário inválido")
    stored.revoked = True
    access = create_access_token(str(user.id))
    new_refresh, jti, expires = create_refresh_token(str(user.id))
    db.add(RefreshToken(user_id=user.id, token_jti=jti, expires_at=expires.replace(tzinfo=None)))
    db.commit()
    _cookies(response, access, new_refresh)
    return {"access_token": access, "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60}


@router.post("/logout", status_code=204)
def logout(response: Response, db: Session = Depends(get_db), refresh_token: str | None = None):
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
    response.delete_cookie("refresh_token", path="/auth")
