from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Pager, get_current_user, paged
from app.core.database import get_db
from app.models.models import BookingStatus, ResourceStatus, ResourceType
from app.schemas import BookingIn, BookingOut, BookingUpdate, Page, ResourceIn, ResourceOut, ResourceUpdate
from app.services import resources as svc

router = APIRouter(prefix="/api", tags=["resources"])


@router.post("/resources", response_model=ResourceOut, status_code=201)
def create_resource(data: ResourceIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_resource(db, user, data)


@router.get("/resources", response_model=Page[ResourceOut])
def list_resources(organization_id: Optional[int] = None, status: Optional[ResourceStatus] = None, type: Optional[ResourceType] = None,
                   search: Optional[str] = None, sort: Optional[str] = None, p: Pager = Depends(),
                   user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = svc.search_resources(db, user, organization_id=organization_id, status=status, type_=type, search=search, sort=sort, page=p.page, size=p.size)
    return paged(items, total, p)


@router.get("/resources/{rid}", response_model=ResourceOut)
def get_resource(rid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get_resource(db, user, rid)


@router.patch("/resources/{rid}", response_model=ResourceOut)
def update_resource(rid: int, data: ResourceUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.update_resource(db, user, rid, data)


@router.post("/resources/{rid}/activate", response_model=ResourceOut)
def activate(rid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.set_status(db, user, rid, True)


@router.post("/resources/{rid}/deactivate", response_model=ResourceOut)
def deactivate(rid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.set_status(db, user, rid, False)


# ---------------------------------------------------------------- bookings
@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(data: BookingIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_booking(db, user, data)


@router.get("/bookings", response_model=Page[BookingOut])
def list_bookings(organization_id: Optional[int] = None, resource_id: Optional[int] = None, status: Optional[BookingStatus] = None,
                  requested_by: Optional[int] = None, event_id: Optional[int] = None, date_from: Optional[datetime] = None,
                  date_to: Optional[datetime] = None, sort: Optional[str] = None, p: Pager = Depends(),
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = svc.search_bookings(db, user, organization_id=organization_id, resource_id=resource_id, status=status, requested_by=requested_by,
                                      event_id=event_id, date_from=date_from, date_to=date_to, sort=sort, page=p.page, size=p.size)
    return paged(items, total, p)


@router.get("/bookings/{bid}", response_model=BookingOut)
def get_booking(bid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get_booking(db, user, bid)


@router.patch("/bookings/{bid}", response_model=BookingOut)
def update_booking(bid: int, data: BookingUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.update_booking(db, user, bid, data)


@router.post("/bookings/{bid}/cancel", response_model=BookingOut)
def cancel_booking(bid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.cancel(db, user, bid)


@router.post("/bookings/{bid}/approve", response_model=BookingOut)
def approve_booking(bid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.decide(db, user, bid, True)


@router.post("/bookings/{bid}/reject", response_model=BookingOut)
def reject_booking(bid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.decide(db, user, bid, False)
