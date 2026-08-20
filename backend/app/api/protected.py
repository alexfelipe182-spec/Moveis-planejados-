from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_admin
from app.models import User
from app.schemas.user import UserRead

router = APIRouter(tags=["Security"])


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/admin/check")
def admin_check(_: User = Depends(require_admin)):
    return {"status": "ok", "message": "Acesso administrativo autorizado"}
