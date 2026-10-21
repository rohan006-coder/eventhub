import re

from app.core.errors import forbidden, not_found
from app.models.models import Comment, NotificationType as N
from app.repositories import CommentRepo, MemberRepo, SessionRepo, UserRepo
from app.services import notifications as notif
from app.services.audit import audit
from app.services.permissions import get_event_visible

MENTION_RE = re.compile(r"(?<![\w.@])@([A-Za-z0-9_.-]{3,50})")


def extract_mentions(body: str) -> list[str]:
    return list(dict.fromkeys(x.rstrip(".-").lower() for x in MENTION_RE.findall(body)))


def create(db, user, data):
    ev, _ = get_event_visible(db, user, data.event_id)
    if data.session_id:
        s = SessionRepo(db).get(data.session_id)
        if not s or s.event_id != ev.id:
            raise not_found("Session")
    c = CommentRepo(db).add(Comment(event_id=ev.id, session_id=data.session_id, user_id=user.id, body=data.body))
    # Only notify people who actually belong to the organization (no probing of other tenants' users).
    members = set(MemberRepo(db).user_ids(ev.organization_id))
    mentioned = [u for u in UserRepo(db).by_usernames(extract_mentions(data.body)) if u.id in members and u.id != user.id]
    pushes = notif.notify(db, [u.id for u in mentioned], N.user_mentioned, f"{user.full_name} mentioned you", data.body[:200],
                          org_id=ev.organization_id, data={"event_id": ev.id, "session_id": data.session_id, "comment_id": c.id})
    audit(db, user, "comment.create", "comment", c.id, ev.organization_id)
    db.commit()
    notif.push(pushes)
    notif.broadcast(members, "comment.created", {"event_id": ev.id, "session_id": data.session_id, "comment_id": c.id})
    return c


def list_for(db, user, event_id, session_id, page, size):
    ev, _ = get_event_visible(db, user, event_id)
    return CommentRepo(db).list(ev.id, session_id, page, size)


def _own(db, user, cid):
    c = CommentRepo(db).get(cid)
    if not c:
        raise not_found("Comment")
    ev, role = get_event_visible(db, user, c.event_id)
    return c, ev, role


def update(db, user, cid, body):
    c, ev, _ = _own(db, user, cid)
    if c.user_id != user.id:
        raise forbidden("FORBIDDEN", "You can only edit your own comments.")
    c.body = body
    db.commit()
    return c


def delete(db, user, cid):
    c, ev, _ = _own(db, user, cid)
    if c.user_id != user.id:
        raise forbidden("FORBIDDEN", "You can only delete your own comments.")
    CommentRepo(db).delete(c)
    db.commit()
