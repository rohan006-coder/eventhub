import logging

from sqlalchemy.orm import Session

from app.core.errors import forbidden, not_found
from app.models.models import Notification, NotificationType
from app.repositories import NotificationRepo
from app.services.realtime import manager

log = logging.getLogger("eventhub.mail")


def notify(db: Session, user_ids, ntype: NotificationType, title: str, message: str = "", *, org_id=None, data=None) -> list[Notification]:
    """Persist notifications (caller commits) and push them live once flushed."""
    repo, out = NotificationRepo(db), []
    for uid in dict.fromkeys(user_ids):
        out.append(repo.add(Notification(user_id=uid, organization_id=org_id, type=ntype, title=title, message=message, data=data or {})))
    return out


def push(notifications: list[Notification], event_name: str = "notification"):
    """Call after commit."""
    for n in notifications:
        manager.publish([n.user_id], {"event": event_name, "data": {"id": n.id, "type": n.type.value, "title": n.title,
                                                                  "message": n.message, "data": n.data}})


def broadcast(user_ids, event_name: str, data: dict):
    manager.publish(list(user_ids), {"event": event_name, "data": data})


def send_email(to_user_id: int, subject: str):
    """Background-task stub: wire SMTP/SES here. Logged so the flow is visible in dev."""
    log.info("EMAIL to user=%s subject=%s", to_user_id, subject)


def list_for(db, user, unread_only, page, size):
    return NotificationRepo(db).list(user.id, unread_only, page, size)


def mark_read(db, user, nid):
    n = NotificationRepo(db).get(nid)
    if not n:
        raise not_found("Notification")
    if n.user_id != user.id:
        raise forbidden("FORBIDDEN", "You cannot modify another user's notification.")
    n.is_read = True
    db.commit()
    return n


def mark_all_read(db, user):
    n = NotificationRepo(db).mark_all(user.id)
    db.commit()
    return n
