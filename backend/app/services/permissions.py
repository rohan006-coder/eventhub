"""Central authorization rules: organization isolation + role hierarchy + resource ownership."""
from app.core.errors import forbidden, not_found
from app.repositories import EventRepo, MemberRepo

RANK = {"participant": 1, "staff": 2, "event_manager": 3, "org_admin": 4}


def require_role(db, user, org_id: int, min_role: str = "participant") -> str:
    """Returns the caller's effective role in the org or raises 403. Super admins act as org_admin everywhere."""
    if user.is_super_admin:
        return "org_admin"
    mem = MemberRepo(db).get_for(org_id, user.id)
    if not mem or not mem.is_active:
        raise forbidden("ORGANIZATION_ACCESS_DENIED", "You do not have access to this organization.")
    if RANK[mem.role] < RANK[min_role]:
        raise forbidden("INSUFFICIENT_PERMISSIONS", f"This action requires the '{min_role}' role or higher.")
    return mem.role


def role_in(db, user, org_id: int):
    try:
        return require_role(db, user, org_id)
    except Exception:
        return None


def get_event_visible(db, user, event_id: int, min_role: str = "participant"):
    """Load an event the caller may see. Participants cannot see drafts (reported as not found)."""
    ev = EventRepo(db).get(event_id)
    if not ev:
        raise not_found("Event")
    role = require_role(db, user, ev.organization_id, min_role)
    if role == "participant" and ev.status.value == "draft":
        raise not_found("Event")
    return ev, role


def get_event_managed(db, user, event_id: int):
    """Event-level authorization: managers may only change events they organize; org admins may change any."""
    ev = EventRepo(db).get(event_id)
    if not ev:
        raise not_found("Event")
    role = require_role(db, user, ev.organization_id, "event_manager")
    if role != "org_admin" and ev.organizer_id != user.id:
        raise forbidden("EVENT_ACCESS_DENIED", "Only the event organizer or an organization admin can do this.")
    return ev, role


def org_ids_with_role(db, user, min_role: str = "participant") -> list[int]:
    """Every org in which the caller holds at least `min_role` (all orgs for super admins)."""
    from app.repositories import OrgRepo
    if user.is_super_admin:
        return [o.id for o in OrgRepo(db).all()]
    return [o.id for o, r in OrgRepo(db).for_user(user.id) if RANK[r] >= RANK[min_role]]
