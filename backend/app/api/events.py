from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import Pager, get_current_user, paged
from app.core.database import get_db
from app.models.models import AttendanceStatus, EventStatus
from app.schemas import (AttendanceIn, AttendanceOut, AttendanceUpdate, EventIn, EventOut, EventUpdate, Page, SessionIn, SessionOut,
                         SessionUpdate, SpeakerIn, SpeakerOut, SpeakerUpdate, TransitionIn)
from app.services import attendance as att_svc, events as svc, sessions as ses_svc

router = APIRouter(prefix="/api", tags=["events"])


# ---------------------------------------------------------------- events
@router.post("/events", response_model=EventOut, status_code=201)
def create_event(data: EventIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create(db, user, data)


@router.get("/events", response_model=Page[EventOut])
def list_events(organization_id: Optional[int] = None, status: Optional[EventStatus] = None, organizer_id: Optional[int] = None,
                location: Optional[str] = None, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                search: Optional[str] = Query(None, max_length=100), sort: Optional[str] = None,
                p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = svc.search(db, user, organization_id=organization_id, status=status, organizer_id=organizer_id, location=location,
                              date_from=date_from, date_to=date_to, search=search, sort=sort, page=p.page, size=p.size)
    return paged(items, total, p)


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get(db, user, event_id)


@router.patch("/events/{event_id}", response_model=EventOut)
def update_event(event_id: int, data: EventUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.update(db, user, event_id, data)


@router.post("/events/{event_id}/publish", response_model=EventOut)
def publish(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.transition(db, user, event_id, EventStatus.published)


@router.post("/events/{event_id}/cancel", response_model=EventOut)
def cancel(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.transition(db, user, event_id, EventStatus.cancelled)


@router.post("/events/{event_id}/archive", response_model=EventOut)
def archive(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.transition(db, user, event_id, EventStatus.archived)


@router.post("/events/{event_id}/transition", response_model=EventOut)
def transition(event_id: int, data: TransitionIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.transition(db, user, event_id, data.status)


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc.delete(db, user, event_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- sessions
@router.post("/events/{event_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(event_id: int, data: SessionIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ses_svc.create(db, user, event_id, data)


@router.get("/events/{event_id}/sessions", response_model=list[SessionOut])
def list_sessions(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ses_svc.list_for_event(db, user, event_id)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ses_svc.get(db, user, session_id)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(session_id: int, data: SessionUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ses_svc.update(db, user, session_id, data)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ses_svc.delete(db, user, session_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- speakers
@router.post("/speakers", response_model=SpeakerOut, status_code=201)
def create_speaker(data: SpeakerIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ses_svc.speaker_create(db, user, data)


@router.get("/speakers", response_model=Page[SpeakerOut])
def list_speakers(organization_id: Optional[int] = None, search: Optional[str] = None, sort: Optional[str] = None,
                  p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = ses_svc.speaker_search(db, user, organization_id, p.page, p.size, search=search, sort=sort)
    return paged(items, total, p)


@router.get("/speakers/{speaker_id}", response_model=SpeakerOut)
def get_speaker(speaker_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ses_svc.speaker_get(db, user, speaker_id)


@router.patch("/speakers/{speaker_id}", response_model=SpeakerOut)
def update_speaker(speaker_id: int, data: SpeakerUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ses_svc.speaker_update(db, user, speaker_id, data)


@router.delete("/speakers/{speaker_id}", status_code=204)
def delete_speaker(speaker_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ses_svc.speaker_delete(db, user, speaker_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- attendance
@router.post("/events/{event_id}/attendance", response_model=AttendanceOut, status_code=201)
def mark_attendance(event_id: int, data: AttendanceIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return att_svc.mark(db, user, event_id, data)


@router.get("/events/{event_id}/attendance", response_model=Page[AttendanceOut])
def list_attendance(event_id: int, p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = att_svc.list_for_event(db, user, event_id, p.page, p.size)
    return paged(items, total, p)


@router.patch("/attendance/{attendance_id}", response_model=AttendanceOut)
def update_attendance(attendance_id: int, data: AttendanceUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return att_svc.update(db, user, attendance_id, data.status)


@router.get("/events/{event_id}/attendance-report")
def attendance_report(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    csv_text = att_svc.report_csv(db, user, event_id)
    return Response(csv_text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="attendance-{event_id}.csv"'})
