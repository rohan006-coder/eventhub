from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Pager, get_current_user, paged
from app.core.database import get_db
from app.models.models import RegistrationStatus
from app.schemas import Page, RegisterEventIn, RegistrationOut
from app.services import registrations as svc

router = APIRouter(prefix="/api", tags=["registrations"])


@router.post("/events/{event_id}/register", response_model=RegistrationOut, status_code=201)
def register(event_id: int, data: RegisterEventIn = RegisterEventIn(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.register(db, user, event_id, data.notes)


@router.get("/events/{event_id}/registrations", response_model=Page[RegistrationOut])
def event_registrations(event_id: int, status: Optional[RegistrationStatus] = None, participant_id: Optional[int] = None,
                        date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, sort: Optional[str] = None,
                        p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = svc.list_for_event(db, user, event_id, p.page, p.size, status, participant_id, date_from, date_to, sort)
    return paged(items, total, p)


@router.get("/registrations", response_model=Page[RegistrationOut])
def search_registrations(organization_id: Optional[int] = None, event_id: Optional[int] = None, status: Optional[RegistrationStatus] = None,
                         participant_id: Optional[int] = None, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                         sort: Optional[str] = None, p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = svc.search(db, user, organization_id=organization_id, event_id=event_id, status=status, participant_id=participant_id,
                              date_from=date_from, date_to=date_to, sort=sort, page=p.page, size=p.size)
    return paged(items, total, p)


@router.get("/registrations/{reg_id}", response_model=RegistrationOut)
def get_registration(reg_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get(db, user, reg_id)


@router.post("/registrations/{reg_id}/cancel", response_model=RegistrationOut)
def cancel(reg_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.cancel(db, user, reg_id)


@router.post("/registrations/{reg_id}/approve", response_model=RegistrationOut)
def approve(reg_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.approve(db, user, reg_id)


@router.post("/registrations/{reg_id}/reject", response_model=RegistrationOut)
def reject(reg_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.reject(db, user, reg_id)
