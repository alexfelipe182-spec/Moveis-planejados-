from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + expires_delta
    jti = str(uuid4())
    payload = {"sub": subject, "type": token_type, "jti": jti, "iat": now, "exp": expires}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm), jti, expires


def create_access_token(subject: str) -> str:
    token, _, _ = _create_token(subject, "access", timedelta(minutes=settings.access_token_expire_minutes))
    return token


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    return _create_token(subject, "refresh", timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Token inválido ou expirado") from exc
