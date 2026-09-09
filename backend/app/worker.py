"""python -m app.worker [--once] [--schedule-only] [--poll-seconds 5]."""
import argparse
import signal
import threading
import time

from sqlalchemy import select

from app.core.observability import record_event
from app.database import SessionLocal
from app.models import AutomationJob, Subscription
from app.models.tenant import utc_now_naive
from app.services.automation import process_job, schedule_trial


def run_once(factory=SessionLocal) -> bool:
    with factory() as db, db.begin():
        # Unscoped discovery is restricted to this internal worker entry point.
        job = db.scalar(select(AutomationJob).where(
            AutomationJob.status.in_(["pending", "retry"]),
            AutomationJob.available_at <= utc_now_naive(),
        ).order_by(AutomationJob.available_at, AutomationJob.id).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return False
        db.info["tenant_id"] = job.tenant_id
        process_job(db, job)
    return True


def schedule_due_trials(factory=SessionLocal) -> int:
    with factory() as db:
        rows = db.execute(select(Subscription.id, Subscription.tenant_id).where(
            Subscription.status == "trialing", Subscription.trial_end <= utc_now_naive(),
        ).order_by(Subscription.id).limit(500)).all()
    for subscription_id, tenant_id in rows:
        with factory(info={"tenant_id": tenant_id}) as db, db.begin():
            subscription = db.get(Subscription, subscription_id)
            if subscription and subscription.status == "trialing" and subscription.trial_end:
                schedule_trial(db, subscription)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--schedule-only", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args()
    if args.poll_seconds < 0.1:
        parser.error("--poll-seconds deve ser >= 0.1")
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    next_schedule = 0.0
    while not stopped.is_set():
        try:
            if time.monotonic() >= next_schedule:
                schedule_due_trials()
                next_schedule = time.monotonic() + 60
            if args.schedule_only:
                return
            processed = run_once()
            if args.once:
                return
            if processed:
                continue
        except Exception:
            # Connection/commit failures roll back. Restart or next poll reclaims the job.
            record_event("worker.failed", result="retry", error_code="database_unavailable")
            if args.once or args.schedule_only:
                raise SystemExit(1) from None
        stopped.wait(args.poll_seconds)


if __name__ == "__main__":
    main()
