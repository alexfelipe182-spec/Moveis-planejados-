from uuid import uuid4

from sqlalchemy import create_engine, event
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

    statement = execute_state.statement
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if issubclass(model, TenantScopedMixin):
            statement = statement.options(
                with_loader_criteria(
                    model,
                    lambda cls, tenant_id=tenant_id: cls.tenant_id == tenant_id,
                    include_aliases=True,
                )
            )
    execute_state.statement = statement


@event.listens_for(Session, "before_flush")
def _assign_tenant_id(session: Session, _flush_context, _instances) -> None:
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
