from uuid import uuid4

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=10,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "do_orm_execute")
def _tenant_filter(execute_state) -> None:
    tenant_id = execute_state.session.info.get("tenant_id")
    if not tenant_id or not execute_state.is_select or execute_state.execution_options.get("skip_tenant_scope"):
        return

    from app.models.tenant import TenantScopedMixin

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantScopedMixin,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


def _validate_tenant_references(session: Session, obj) -> None:
    """Reject cross-tenant foreign-key links before they reach PostgreSQL."""
    from app.models.tenant import TenantScopedMixin

    if not isinstance(obj, TenantScopedMixin):
        return

    tenant_id = getattr(obj, "tenant_id", None)
    if tenant_id is None:
        return

    connection = session.connection()
    for column in obj.__mapper__.columns:
        if column.key == "tenant_id":
            continue
        value = getattr(obj, column.key, None)
        if value is None:
            continue
        for foreign_key in column.foreign_keys:
            target_column = foreign_key.column
            target_tenant_column = target_column.table.c.get("tenant_id")
            if target_tenant_column is None:
                continue
            target_tenant_id = connection.execute(
                select(target_tenant_column).where(target_column == value)
            ).scalar_one_or_none()
            if target_tenant_id is not None and target_tenant_id != tenant_id:
                raise ValueError(
                    f"Referência {column.key} pertence a outra marcenaria"
                )


@event.listens_for(Session, "before_flush")
def _assign_and_validate_tenant(session: Session, _flush_context, _instances) -> None:
    from app.models.tenant import Tenant, TenantScopedMixin
    from app.models.user import User

    for obj in list(session.new):
        if isinstance(obj, User) and obj.tenant_id is None and obj.tenant is None:
            tenant = Tenant(
                name=f"Marcenaria de {obj.name}",
                slug=f"tenant-{uuid4().hex}",
            )
            obj.tenant = tenant
            session.add(tenant)

    tenant_id = session.info.get("tenant_id")
    if not tenant_id:
        for obj in session.identity_map.values():
            if isinstance(obj, User) and obj.tenant_id:
                tenant_id = obj.tenant_id
                session.info["tenant_id"] = tenant_id
                break

    if not tenant_id:
        return

    for obj in session.new:
        if isinstance(obj, TenantScopedMixin):
            current = getattr(obj, "tenant_id", None)
            if current is None:
                obj.tenant_id = tenant_id
            elif current != tenant_id:
                raise ValueError("Tentativa de gravar dados em outra marcenaria")

    for obj in set(session.new).union(session.dirty):
        _validate_tenant_references(session, obj)


@event.listens_for(Session, "after_flush_postexec")
def _remember_new_user_tenant(session: Session, _flush_context) -> None:
    if session.info.get("tenant_id"):
        return

    from app.models.user import User

    for obj in session.identity_map.values():
        if isinstance(obj, User) and obj.tenant_id:
            session.info["tenant_id"] = obj.tenant_id
            return


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.info.pop("tenant_id", None)
        db.close()
