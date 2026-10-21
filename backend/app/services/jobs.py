"""Periodic background jobs (run by the in-process scheduler; safe to run from Celery beat instead)."""
import logging
from datetime import timedelta

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.models.models import BookingStatus, EventStatus, NotificationType as N, RegistrationStatus as R
from app.repositories import ACTIVE_REG, BookingRepo, EventRepo, RegistrationRepo
from app.services import notifications as notif

log = logging.getLogger("eventhub.jobs")


def send_event_reminders(db) -> int:
    now = utcnow()
    count = 0
    for ev in EventRepo(db).due_for_reminder(now, now + timedelta(hours=settings.REMINDER_WINDOW_HOURS)):
        regs, _ = RegistrationRepo(db).search(event_id=ev.id, size=100000)
        ids = [r.user_id for r in regs if r.status in (R.confirmed, R.pending)]
        ev.reminder_sent = True
        pushes = notif.notify(db, ids, N.event_starting_soon, f"Starting soon: {ev.name}", f"Starts {ev.start_time:%Y-%m-%d %H:%M} UTC",
                              org_id=ev.organization_id, data={"event_id": ev.id})
        db.commit()
        notif.push(pushes)
        count += len(pushes)
    return count


def advance_event_statuses(db) -> int:
    now, n = utcnow(), 0
    for ev in EventRepo(db).to_start(now):
        ev.status, n = EventStatus.ongoing, n + 1
    for ev in EventRepo(db).to_complete(now):
        ev.status, n = EventStatus.completed, n + 1
    db.commit()
    return n


def complete_bookings(db) -> int:
    rows = BookingRepo(db).to_complete(utcnow())
    for b in rows:
        b.status = BookingStatus.completed
    db.commit()
    return len(rows)


def run_all():
    db = SessionLocal()
    try:
        r = {"reminders": send_event_reminders(db), "status_changes": advance_event_statuses(db), "bookings_completed": complete_bookings(db)}
        log.info("periodic jobs: %s", r)
        return r
    except Exception:
        db.rollback()
        log.exception("periodic jobs failed")
    finally:
        db.close()
