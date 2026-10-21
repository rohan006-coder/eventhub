from app.core.database import locked
from app.core.errors import AppError, conflict, not_found
from app.models.models import EventSession, EventStatus as S, NotificationType as N, ResourceStatus, Speaker
from app.repositories import RegistrationRepo, ResourceRepo, SessionRepo, SpeakerRepo, ACTIVE_REG
from app.services import notifications as notif
from app.services.audit import audit
from app.services.permissions import get_event_managed, get_event_visible, require_role

OPEN_FOR_SESSIONS = (S.draft, S.published, S.ongoing)


def _validate(db, ev, start, end, room_id, capacity, speaker_ids, exclude_id=None):
    if end <= start:
        raise AppError(422, "INVALID_SESSION_TIME", "Session end time must be after its start time.")
    if start < ev.start_time or end > ev.end_time:
        raise AppError(422, "SESSION_OUTSIDE_EVENT", "A session must take place within the event's start and end time.")
    repo = SessionRepo(db)
    if room_id:
        room = ResourceRepo(db).get(room_id)
        if not room or room.organization_id != ev.organization_id:
            raise not_found("Room")
        if room.status != ResourceStatus.active:
            raise conflict("RESOURCE_INACTIVE", "The selected room is not active.")
        if capacity and room.capacity is not None and capacity > room.capacity:
            raise AppError(422, "SESSION_CAPACITY_EXCEEDED", f"Session capacity cannot exceed the room capacity ({room.capacity}).")
        if repo.room_conflicts(room_id, start, end, exclude_id):
            raise conflict("SESSION_TIME_CONFLICT", "Another session already uses this room at that time.")
    speakers = []
    if speaker_ids:
        speakers = SpeakerRepo(db).many(list(set(speaker_ids)))
        if len(speakers) != len(set(speaker_ids)) or any(s.organization_id != ev.organization_id for s in speakers):
            raise not_found("Speaker")
        if repo.speaker_conflicts([s.id for s in speakers], start, end, exclude_id):
            raise conflict("SPEAKER_TIME_CONFLICT", "A speaker is already assigned to an overlapping session.")
    return speakers


def create(db, user, event_id, data):
    ev, _ = get_event_managed(db, user, event_id)
    if ev.status == S.cancelled:
        raise conflict("EVENT_CANCELLED", "Cancelled events cannot receive new sessions.")
    if ev.status not in OPEN_FOR_SESSIONS:
        raise conflict("INVALID_EVENT_STATUS", f"Sessions cannot be added to a {ev.status.value} event.")
    with locked(db, f"schedule:{ev.organization_id}"):
        speakers = _validate(db, ev, data.start_time, data.end_time, data.room_id, data.capacity, data.speaker_ids)
        s = SessionRepo(db).add(EventSession(event_id=ev.id, title=data.title, description=data.description, start_time=data.start_time,
                                             end_time=data.end_time, room_id=data.room_id, capacity=data.capacity, speakers=speakers))
        audit(db, user, "session.create", "session", s.id, ev.organization_id)
        db.commit()
    return s


def _load(db, user, sid, managed=False):
    s = SessionRepo(db).get(sid)
    if not s:
        raise not_found("Session")
    ev = get_event_managed(db, user, s.event_id)[0] if managed else get_event_visible(db, user, s.event_id)[0]
    return s, ev


def get(db, user, sid):
    return _load(db, user, sid)[0]


def list_for_event(db, user, event_id):
    ev, _ = get_event_visible(db, user, event_id)
    return SessionRepo(db).for_event(ev.id)


def update(db, user, sid, data):
    s, ev = _load(db, user, sid, managed=True)
    if ev.status == S.cancelled:
        raise conflict("EVENT_CANCELLED", "Sessions of a cancelled event cannot be changed.")
    if ev.status not in OPEN_FOR_SESSIONS:
        raise conflict("INVALID_EVENT_STATUS", f"Sessions of a {ev.status.value} event cannot be changed.")
    patch = data.model_dump(exclude_unset=True)
    with locked(db, f"schedule:{ev.organization_id}"):
        start, end = patch.get("start_time", s.start_time), patch.get("end_time", s.end_time)
        room_id = patch["room_id"] if "room_id" in patch else s.room_id
        capacity = patch["capacity"] if "capacity" in patch else s.capacity
        speaker_ids = patch["speaker_ids"] if patch.get("speaker_ids") is not None else [x.id for x in s.speakers]
        speakers = _validate(db, ev, start, end, room_id, capacity, speaker_ids, exclude_id=s.id)
        for k in ("title", "description", "start_time", "end_time", "room_id", "capacity"):
            if k in patch:
                setattr(s, k, patch[k])
        if patch.get("speaker_ids") is not None:
            s.speakers = speakers
        audit(db, user, "session.update", "session", s.id, ev.organization_id)
        regs, _t = RegistrationRepo(db).search(event_id=ev.id, size=100000)
        pushes = notif.notify(db, [r.user_id for r in regs if r.status in ACTIVE_REG], N.session_updated, f"Session updated: {s.title}",
                              f"A session of {ev.name} was changed.", org_id=ev.organization_id, data={"event_id": ev.id, "session_id": s.id})
        db.commit()
    notif.push(pushes)
    return s


def delete(db, user, sid):
    s, ev = _load(db, user, sid, managed=True)
    audit(db, user, "session.delete", "session", s.id, ev.organization_id)
    SessionRepo(db).delete(s)
    db.commit()


# ------------------------------------------------------------------ speakers
def speaker_create(db, user, data):
    require_role(db, user, data.organization_id, "event_manager")
    sp = SpeakerRepo(db).add(Speaker(**data.model_dump()))
    audit(db, user, "speaker.create", "speaker", sp.id, sp.organization_id)
    db.commit()
    return sp


def speaker_get(db, user, spid, min_role="participant"):
    sp = SpeakerRepo(db).get(spid)
    if not sp:
        raise not_found("Speaker")
    require_role(db, user, sp.organization_id, min_role)
    return sp


def speaker_search(db, user, organization_id=None, page=1, size=20, **filters):
    from app.services.permissions import org_ids_with_role
    if organization_id:
        require_role(db, user, organization_id)
        org_ids = [organization_id]
    else:
        org_ids = org_ids_with_role(db, user)
    return SpeakerRepo(db).search(org_ids, page=page, size=size, **filters)


def speaker_update(db, user, spid, data):
    sp = speaker_get(db, user, spid, "event_manager")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(sp, k, v)
    audit(db, user, "speaker.update", "speaker", sp.id, sp.organization_id)
    db.commit()
    return sp


def speaker_delete(db, user, spid):
    sp = speaker_get(db, user, spid, "event_manager")
    audit(db, user, "speaker.delete", "speaker", sp.id, sp.organization_id)
    SpeakerRepo(db).delete(sp)
    db.commit()
