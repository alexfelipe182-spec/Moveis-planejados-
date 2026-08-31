"""Real row-lock checks, only on explicitly enabled disposable test PostgreSQL.

GitHub CI runs these automatically. To opt in locally, set ENVIRONMENT=test and
RUN_POSTGRES_CONCURRENCY_TESTS=1 with a disposable local PostgreSQL database that
already has the migrations. Never point this test at production. SQLite cannot
prove PostgreSQL row-lock behavior.
"""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.api import quote_decisions, quote_items, routes
from app.core.config import settings
from app.database import SessionLocal
from app.models import Activity, Customer, Organization, Quote, User
from app.schemas import QuoteUpdate


test_url = make_url(settings.database_url)
enabled = os.getenv("CI") == "true" or os.getenv("RUN_POSTGRES_CONCURRENCY_TESTS") == "1"
pytestmark = pytest.mark.skipif(
    not (
        enabled
        and settings.environment == "test"
        and test_url.get_backend_name() == "postgresql"
        and test_url.host in {"127.0.0.1", "localhost", "postgres", "db"}
    ),
    reason="Requires explicitly enabled disposable local PostgreSQL in ENVIRONMENT=test",
)


@pytest.fixture
def quote_rows():
    identifier = uuid4().hex
    with SessionLocal() as db:
        organization = Organization(name=f"Lock test {identifier}", slug=f"lock-test-{identifier}")
        customer = Customer(name=f"Concurrency test {identifier}")
        user = User(
            name="Concurrency test",
            email=f"quote-lock-{identifier}@example.com",
            password_hash="test-only-no-login",
            is_admin=True,
        )
        db.add(organization)
        db.flush()
        customer.organization_id = organization.id
        user.organization_id = organization.id
        db.add_all([customer, user])
        db.flush()
        quote = Quote(organization_id=organization.id, customer_id=customer.id, description="Disposable lock test", status="analysis")
        db.add(quote)
        db.commit()
        ids = SimpleNamespace(organization=organization.id, customer=customer.id, user=user.id, quote=quote.id)
    try:
        yield ids
    finally:
        # Only this fixture's newly inserted rows are removed; no shared fixtures
        # or tables are truncated, recreated or dropped.
        with SessionLocal() as db:
            db.execute(delete(Activity).where(Activity.user_id == ids.user))
            db.execute(delete(Quote).where(Quote.id == ids.quote))
            db.execute(delete(Customer).where(Customer.id == ids.customer))
            db.execute(delete(User).where(User.id == ids.user))
            db.execute(delete(Organization).where(Organization.id == ids.organization))
            db.commit()


OPERATIONS = [
    ("edit", "analysis", "approved"),
    ("items", "analysis", "approved"),
    ("decision", "analysis", "approved"),
    ("share", "approved", "sent"),
    ("commercial", "sent", "accepted"),
]


def invoke(operation, db, ids):
    user = SimpleNamespace(id=ids.user, organization_id=ids.organization)
    if operation == "edit":
        return routes.update_quote(ids.quote, QuoteUpdate(description="Revised test quote"), user, db)
    if operation == "items":
        return quote_items._get_editable_quote(db, ids.quote, ids.organization)
    if operation == "decision":
        return quote_decisions.decide_quote(
            ids.quote, quote_decisions.QuoteDecisionRequest(status="approved"), user, db
        )
    if operation == "share":
        return quote_decisions.record_quote_share(ids.quote, user, db)
    return quote_decisions.update_quote_commercial_status(
        ids.quote, quote_decisions.QuoteCommercialStatusRequest(status="accepted"), user, db
    )


def initial_status(ids, value):
    with SessionLocal() as db:
        db.get(Quote, ids.quote).status = value
        db.commit()


@pytest.mark.parametrize(("operation", "initial", "settled"), OPERATIONS)
def test_competing_operation_waits_at_select_for_update(quote_rows, operation, initial, settled):
    initial_status(quote_rows, initial)
    with SessionLocal() as writer, SessionLocal() as contender:
        # Keep a stale identity-map entry in the second transaction as well.
        cached = contender.get(Quote, quote_rows.quote)
        assert cached.status == initial
        locked = writer.get(Quote, quote_rows.quote, with_for_update=True)
        locked.status = settled
        writer.flush()

        # Deterministic bounded contention: no worker threads, scheduling races
        # or sleeps. PostgreSQL must block at SELECT, not only at a later UPDATE.
        contender.execute(text("SET LOCAL lock_timeout = '150ms'"))
        contender.execute(text("SET LOCAL statement_timeout = '2s'"))
        with pytest.raises(OperationalError) as failure:
            invoke(operation, contender, quote_rows)
        assert getattr(failure.value.orig, "sqlstate", None) == "55P03"
        assert "FOR UPDATE" in failure.value.statement.upper()
        contender.rollback()
        writer.commit()

        with pytest.raises(HTTPException) as conflict:
            invoke(operation, contender, quote_rows)
        assert conflict.value.status_code == 409
        contender.rollback()


@pytest.mark.parametrize(("operation", "initial", "settled"), OPERATIONS)
def test_operation_refreshes_stale_state_after_other_transaction_commits(quote_rows, operation, initial, settled):
    initial_status(quote_rows, initial)
    with SessionLocal() as contender, SessionLocal() as writer:
        cached = contender.get(Quote, quote_rows.quote)
        assert cached.status == initial
        writer.get(Quote, quote_rows.quote).status = settled
        writer.commit()
        assert cached.status == initial

        with pytest.raises(HTTPException) as conflict:
            invoke(operation, contender, quote_rows)
        assert conflict.value.status_code == 409
        assert cached.status == settled
        contender.rollback()
