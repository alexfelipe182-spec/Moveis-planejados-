from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_cookie_csrf
from app.core.config import settings
from app.database import get_db
from app.models import Category, Customer, Product, Quote, User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/dashboard")
def dashboard(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "app_name": settings.app_name,
        "counts": {
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "categories": db.scalar(select(func.count()).select_from(Category)) or 0,
            "products": db.scalar(select(func.count()).select_from(Product)) or 0,
            "customers": db.scalar(select(func.count()).select_from(Customer)) or 0,
            "quotes": db.scalar(select(func.count()).select_from(Quote)) or 0,
        },
    }


@router.get("/users", response_model=list[UserRead])
def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.scalars(select(User).order_by(User.id).offset(offset).limit(limit)).all()


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_admin), Depends(require_cookie_csrf)],
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes:
        changes["email"] = str(changes["email"]).lower()
        existing = db.scalar(select(User).where(User.email == changes["email"], User.id != user.id))
        if existing:
            raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    if user.id == current_user.id and changes.get("is_admin") is False:
        raise HTTPException(status_code=400, detail="O administrador atual não pode remover a própria permissão")
    if user.id == current_user.id and changes.get("is_active") is False:
        raise HTTPException(status_code=400, detail="O administrador atual não pode desativar a própria conta")

    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
