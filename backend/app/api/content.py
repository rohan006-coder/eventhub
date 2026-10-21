from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import Pager, get_current_user, paged
from app.core.database import get_db
from app.schemas import AttachmentOut, CommentIn, CommentOut, CommentUpdate, NotificationOut, Page
from app.services import comments as com_svc, dashboard as dash_svc, files as file_svc, notifications as notif_svc

router = APIRouter(prefix="/api", tags=["content"])


# ---------------------------------------------------------------- files
@router.post("/events/{event_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload(event_id: int, entity_type: str = Form("event"), entity_id: Optional[int] = Form(None), file: UploadFile = File(...),
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    content = await file_svc.read_limited(file)
    return file_svc.save(db, user, event_id, entity_type, entity_id or (event_id if entity_type == "event" else 0),
                         file.filename or "", file.content_type or "", content)


@router.get("/events/{event_id}/attachments", response_model=list[AttachmentOut])
def list_files(event_id: int, entity_type: Optional[str] = None, entity_id: Optional[int] = None,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    return file_svc.list_for_event(db, user, event_id, entity_type, entity_id)


@router.get("/attachments/{att_id}/download")
def download(att_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    att = file_svc.get_for_download(db, user, att_id)
    return FileResponse(att.storage_path, media_type=att.mime_type, filename=att.file_name,
                        headers={"X-Content-Type-Options": "nosniff"}, content_disposition_type="attachment")


@router.delete("/attachments/{att_id}", status_code=204)
def delete_file(att_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    file_svc.delete(db, user, att_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- comments
@router.post("/comments", response_model=CommentOut, status_code=201)
def add_comment(data: CommentIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return com_svc.create(db, user, data)


@router.get("/comments", response_model=Page[CommentOut])
def list_comments(event_id: int, session_id: Optional[int] = None, p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = com_svc.list_for(db, user, event_id, session_id, p.page, p.size)
    return paged(items, total, p)


@router.patch("/comments/{cid}", response_model=CommentOut)
def edit_comment(cid: int, data: CommentUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return com_svc.update(db, user, cid, data.body)


@router.delete("/comments/{cid}", status_code=204)
def delete_comment(cid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    com_svc.delete(db, user, cid)
    return Response(status_code=204)


# ---------------------------------------------------------------- notifications
@router.get("/notifications", response_model=Page[NotificationOut])
def notifications(unread_only: bool = False, p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = notif_svc.list_for(db, user, unread_only, p.page, p.size)
    return paged(items, total, p)


@router.get("/notifications/unread-count")
def unread_count(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.repositories import NotificationRepo
    return {"count": NotificationRepo(db).unread_count(user.id)}


@router.patch("/notifications/read-all")
def read_all(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"updated": notif_svc.mark_all_read(db, user)}


@router.patch("/notifications/{nid}/read", response_model=NotificationOut)
def read_one(nid: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return notif_svc.mark_read(db, user, nid)


# ---------------------------------------------------------------- dashboard & calendar
@router.get("/dashboard")
def dashboard(organization_id: Optional[int] = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return dash_svc.build(db, user, organization_id)


@router.get("/calendar")
def calendar(organization_id: int, start: datetime, end: datetime, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.schemas import _utc
    return dash_svc.calendar(db, user, organization_id, _utc(start), _utc(end))
