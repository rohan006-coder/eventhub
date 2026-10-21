"""Data-access layer. Repositories build queries and persist; they hold no business rules."""
from datetime import datetime
from typing import Generic, Optional, TypeVar

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import models as m

T = TypeVar("T")
OPEN_BOOKING = (m.BookingStatus.requested, m.BookingStatus.approved)
SEAT_STATUSES = (m.RegistrationStatus.pending, m.RegistrationStatus.confirmed,
                 m.RegistrationStatus.attended, m.RegistrationStatus.no_show)
ACTIVE_REG = SEAT_STATUSES + (m.RegistrationStatus.waitlisted,)


class Repo(Generic[T]):
    model: type

    def __init__(self, db: Session):
        self.db = db

    def get(self, id_) -> Optional[T]:
        return self.db.get(self.model, id_)

    def add(self, obj: T) -> T:
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj) -> None:
        self.db.delete(obj)
        self.db.flush()

    def paginate(self, stmt, page: int, size: int, order=None):
        total = self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        if order is not None:
            stmt = stmt.order_by(*order)
        items = self.db.scalars(stmt.limit(size).offset((page - 1) * size)).unique().all()
        return items, total


def order_by_param(model, sort: Optional[str], allowed: set[str], default: str):
    """sort='-start_time' -> [desc(start_time), id]; unknown fields fall back to default."""
    field, desc = (sort or default), False
    if field.startswith("-"):
        field, desc = field[1:], True
    if field not in allowed:
        field, desc = default.lstrip("-"), default.startswith("-")
    col = getattr(model, field)
    return [col.desc() if desc else col.asc(), model.id.asc()]


class UserRepo(Repo[m.User]):
    model = m.User

    def by_email(self, email): return self.db.scalar(select(m.User).where(func.lower(m.User.email) == email.lower()))
    def by_username(self, u): return self.db.scalar(select(m.User).where(m.User.username == u.lower()))
    def by_usernames(self, names): return list(self.db.scalars(select(m.User).where(m.User.username.in_([n.lower() for n in names]))))


class RefreshTokenRepo(Repo[m.RefreshToken]):
    model = m.RefreshToken

    def by_hash(self, h): return self.db.scalar(select(m.RefreshToken).where(m.RefreshToken.token_hash == h))

    def revoke_all(self, user_id, now):
        for t in self.db.scalars(select(m.RefreshToken).where(m.RefreshToken.user_id == user_id, m.RefreshToken.revoked_at.is_(None))):
            t.revoked_at = now


class OrgRepo(Repo[m.Organization]):
    model = m.Organization

    def by_name(self, name): return self.db.scalar(select(m.Organization).where(func.lower(m.Organization.name) == name.lower()))

    def for_user(self, user_id):
        stmt = (select(m.Organization, m.OrganizationMember.role).join(m.OrganizationMember)
                .where(m.OrganizationMember.user_id == user_id, m.OrganizationMember.is_active.is_(True)).order_by(m.Organization.name))
        return self.db.execute(stmt).all()

    def all(self): return list(self.db.scalars(select(m.Organization).order_by(m.Organization.name)))


class MemberRepo(Repo[m.OrganizationMember]):
    model = m.OrganizationMember

    def get_for(self, org_id, user_id):
        return self.db.scalar(select(m.OrganizationMember).where(m.OrganizationMember.organization_id == org_id, m.OrganizationMember.user_id == user_id))

    def list(self, org_id, page, size):
        return self.paginate(select(m.OrganizationMember).where(m.OrganizationMember.organization_id == org_id), page, size,
                             [m.OrganizationMember.id.asc()])

    def count_active_admins(self, org_id):
        return self.db.scalar(select(func.count()).select_from(m.OrganizationMember).where(
            m.OrganizationMember.organization_id == org_id, m.OrganizationMember.role == "org_admin", m.OrganizationMember.is_active.is_(True)))

    def user_ids(self, org_id, min_roles=None):
        stmt = select(m.OrganizationMember.user_id).where(m.OrganizationMember.organization_id == org_id, m.OrganizationMember.is_active.is_(True))
        if min_roles:
            stmt = stmt.where(m.OrganizationMember.role.in_(min_roles))
        return list(self.db.scalars(stmt))

    def count(self, org_id):
        return self.db.scalar(select(func.count()).select_from(m.OrganizationMember).where(m.OrganizationMember.organization_id == org_id)) or 0


class EventRepo(Repo[m.Event]):
    model = m.Event
    SORTABLE = {"start_time", "end_time", "created_at", "name", "status"}

    def search(self, org_ids, *, hide_draft_orgs=(), status=None, organizer_id=None, location=None, date_from=None, date_to=None,
               search=None, sort=None, page=1, size=20):
        stmt = select(m.Event).where(m.Event.organization_id.in_(org_ids))
        if hide_draft_orgs:  # participants never see drafts in these orgs
            stmt = stmt.where(~and_(m.Event.organization_id.in_(hide_draft_orgs), m.Event.status == m.EventStatus.draft))
        if status: stmt = stmt.where(m.Event.status == status)
        if organizer_id: stmt = stmt.where(m.Event.organizer_id == organizer_id)
        if location: stmt = stmt.where(m.Event.location.ilike(f"%{location}%"))
        if date_from: stmt = stmt.where(m.Event.end_time >= date_from)
        if date_to: stmt = stmt.where(m.Event.start_time <= date_to)
        if search: stmt = stmt.where(or_(m.Event.name.ilike(f"%{search}%"), m.Event.description.ilike(f"%{search}%")))
        return self.paginate(stmt, page, size, order_by_param(m.Event, sort, self.SORTABLE, "start_time"))

    def due_for_reminder(self, now, until):
        return list(self.db.scalars(select(m.Event).where(m.Event.status == m.EventStatus.published, m.Event.reminder_sent.is_(False),
                                                          m.Event.start_time > now, m.Event.start_time <= until)))

    def to_start(self, now): return list(self.db.scalars(select(m.Event).where(m.Event.status == m.EventStatus.published, m.Event.start_time <= now)))
    def to_complete(self, now): return list(self.db.scalars(select(m.Event).where(m.Event.status == m.EventStatus.ongoing, m.Event.end_time <= now)))


class RegistrationRepo(Repo[m.Registration]):
    model = m.Registration
    SORTABLE = {"created_at", "status", "id"}

    def seat_count(self, event_id):
        return self.db.scalar(select(func.count()).select_from(m.Registration).where(m.Registration.event_id == event_id, m.Registration.status.in_(SEAT_STATUSES))) or 0

    def count_status(self, event_id, status):
        return self.db.scalar(select(func.count()).select_from(m.Registration).where(m.Registration.event_id == event_id, m.Registration.status == status)) or 0

    def active_for(self, event_id, user_id):
        return self.db.scalar(select(m.Registration).where(m.Registration.event_id == event_id, m.Registration.user_id == user_id, m.Registration.status.in_(ACTIVE_REG)))

    def waitlist(self, event_id):
        return list(self.db.scalars(select(m.WaitlistEntry).where(m.WaitlistEntry.event_id == event_id).order_by(m.WaitlistEntry.created_at, m.WaitlistEntry.id)))

    def waitlist_entry(self, reg_id): return self.db.scalar(select(m.WaitlistEntry).where(m.WaitlistEntry.registration_id == reg_id))

    def waitlist_position(self, reg):
        entry = self.waitlist_entry(reg.id)
        if not entry: return None
        return (self.db.scalar(select(func.count()).select_from(m.WaitlistEntry).where(
            m.WaitlistEntry.event_id == reg.event_id,
            or_(m.WaitlistEntry.created_at < entry.created_at, and_(m.WaitlistEntry.created_at == entry.created_at, m.WaitlistEntry.id <= entry.id)))))

    def search(self, *, org_ids=None, user_id=None, event_id=None, status=None, participant_id=None, date_from=None, date_to=None, sort=None, page=1, size=20):
        stmt = select(m.Registration).join(m.Event, m.Event.id == m.Registration.event_id)
        if org_ids is not None: stmt = stmt.where(m.Event.organization_id.in_(org_ids))
        if user_id: stmt = stmt.where(m.Registration.user_id == user_id)
        if event_id: stmt = stmt.where(m.Registration.event_id == event_id)
        if status: stmt = stmt.where(m.Registration.status == status)
        if participant_id: stmt = stmt.where(m.Registration.user_id == participant_id)
        if date_from: stmt = stmt.where(m.Registration.created_at >= date_from)
        if date_to: stmt = stmt.where(m.Registration.created_at <= date_to)
        return self.paginate(stmt, page, size, order_by_param(m.Registration, sort, self.SORTABLE, "-created_at"))


class ResourceRepo(Repo[m.Resource]):
    model = m.Resource
    SORTABLE = {"name", "type", "created_at", "status"}

    def search(self, org_ids, *, status=None, type_=None, search=None, sort=None, page=1, size=20):
        stmt = select(m.Resource).where(m.Resource.organization_id.in_(org_ids))
        if status: stmt = stmt.where(m.Resource.status == status)
        if type_: stmt = stmt.where(m.Resource.type == type_)
        if search: stmt = stmt.where(or_(m.Resource.name.ilike(f"%{search}%"), m.Resource.location.ilike(f"%{search}%")))
        return self.paginate(stmt, page, size, order_by_param(m.Resource, sort, self.SORTABLE, "name"))


class BookingRepo(Repo[m.ResourceBooking]):
    model = m.ResourceBooking
    SORTABLE = {"start_time", "end_time", "created_at", "status"}

    def conflicts(self, resource_id, start, end, exclude_id=None):
        stmt = select(m.ResourceBooking).where(m.ResourceBooking.resource_id == resource_id, m.ResourceBooking.status.in_(OPEN_BOOKING),
                                               m.ResourceBooking.start_time < end, m.ResourceBooking.end_time > start)
        if exclude_id: stmt = stmt.where(m.ResourceBooking.id != exclude_id)
        return list(self.db.scalars(stmt))

    def search(self, org_ids, *, user_id=None, resource_id=None, status=None, date_from=None, date_to=None, requested_by=None,
               event_id=None, sort=None, page=1, size=20):
        stmt = select(m.ResourceBooking).join(m.Resource, m.Resource.id == m.ResourceBooking.resource_id).where(m.Resource.organization_id.in_(org_ids))
        if user_id: stmt = stmt.where(m.ResourceBooking.requested_by == user_id)
        if resource_id: stmt = stmt.where(m.ResourceBooking.resource_id == resource_id)
        if status: stmt = stmt.where(m.ResourceBooking.status == status)
        if requested_by: stmt = stmt.where(m.ResourceBooking.requested_by == requested_by)
        if event_id: stmt = stmt.where(m.ResourceBooking.event_id == event_id)
        if date_from: stmt = stmt.where(m.ResourceBooking.end_time >= date_from)
        if date_to: stmt = stmt.where(m.ResourceBooking.start_time <= date_to)
        return self.paginate(stmt, page, size, order_by_param(m.ResourceBooking, sort, self.SORTABLE, "start_time"))

    def to_complete(self, now):
        return list(self.db.scalars(select(m.ResourceBooking).where(m.ResourceBooking.status == m.BookingStatus.approved, m.ResourceBooking.end_time <= now)))


class SpeakerRepo(Repo[m.Speaker]):
    model = m.Speaker

    def search(self, org_ids, *, search=None, sort=None, page=1, size=20):
        stmt = select(m.Speaker).where(m.Speaker.organization_id.in_(org_ids))
        if search: stmt = stmt.where(or_(m.Speaker.name.ilike(f"%{search}%"), m.Speaker.company.ilike(f"%{search}%")))
        return self.paginate(stmt, page, size, order_by_param(m.Speaker, sort, {"name", "created_at"}, "name"))

    def many(self, ids): return list(self.db.scalars(select(m.Speaker).where(m.Speaker.id.in_(ids)))) if ids else []


class SessionRepo(Repo[m.EventSession]):
    model = m.EventSession

    def for_event(self, event_id):
        return list(self.db.scalars(select(m.EventSession).where(m.EventSession.event_id == event_id).order_by(m.EventSession.start_time, m.EventSession.id)))

    def room_conflicts(self, room_id, start, end, exclude_id=None):
        stmt = select(m.EventSession).where(m.EventSession.room_id == room_id, m.EventSession.start_time < end, m.EventSession.end_time > start)
        if exclude_id: stmt = stmt.where(m.EventSession.id != exclude_id)
        return list(self.db.scalars(stmt))

    def speaker_conflicts(self, speaker_ids, start, end, exclude_id=None):
        if not speaker_ids: return []
        stmt = (select(m.EventSession).join(m.speaker_sessions, m.speaker_sessions.c.session_id == m.EventSession.id)
                .where(m.speaker_sessions.c.speaker_id.in_(speaker_ids), m.EventSession.start_time < end, m.EventSession.end_time > start))
        if exclude_id: stmt = stmt.where(m.EventSession.id != exclude_id)
        return list(self.db.scalars(stmt).unique())


class AttendanceRepo(Repo[m.Attendance]):
    model = m.Attendance

    def by_registration(self, reg_id): return self.db.scalar(select(m.Attendance).where(m.Attendance.registration_id == reg_id))

    def for_event(self, event_id, user_id=None, page=1, size=50):
        stmt = select(m.Attendance).where(m.Attendance.event_id == event_id)
        if user_id: stmt = stmt.where(m.Attendance.user_id == user_id)
        return self.paginate(stmt, page, size, [m.Attendance.id.asc()])


class AttachmentRepo(Repo[m.Attachment]):
    model = m.Attachment

    def for_event(self, event_id, entity_type=None, entity_id=None):
        stmt = select(m.Attachment).where(m.Attachment.event_id == event_id)
        if entity_type: stmt = stmt.where(m.Attachment.entity_type == entity_type)
        if entity_id: stmt = stmt.where(m.Attachment.entity_id == entity_id)
        return list(self.db.scalars(stmt.order_by(m.Attachment.id.desc())))


class CommentRepo(Repo[m.Comment]):
    model = m.Comment

    def list(self, event_id, session_id, page, size):
        stmt = select(m.Comment).where(m.Comment.event_id == event_id)
        stmt = stmt.where(m.Comment.session_id == session_id) if session_id else stmt.where(m.Comment.session_id.is_(None))
        return self.paginate(stmt, page, size, [m.Comment.created_at.asc(), m.Comment.id.asc()])


class NotificationRepo(Repo[m.Notification]):
    model = m.Notification

    def list(self, user_id, unread_only, page, size):
        stmt = select(m.Notification).where(m.Notification.user_id == user_id)
        if unread_only: stmt = stmt.where(m.Notification.is_read.is_(False))
        return self.paginate(stmt, page, size, [m.Notification.created_at.desc(), m.Notification.id.desc()])

    def unread_count(self, user_id):
        return self.db.scalar(select(func.count()).select_from(m.Notification).where(m.Notification.user_id == user_id, m.Notification.is_read.is_(False))) or 0

    def mark_all(self, user_id):
        n = 0
        for x in self.db.scalars(select(m.Notification).where(m.Notification.user_id == user_id, m.Notification.is_read.is_(False))):
            x.is_read = True
            n += 1
        return n


class AuditRepo(Repo[m.AuditLog]):
    model = m.AuditLog

    def list(self, org_id, page, size):
        return self.paginate(select(m.AuditLog).where(m.AuditLog.organization_id == org_id), page, size, [m.AuditLog.id.desc()])
