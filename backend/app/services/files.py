import io
import os
import uuid
import zipfile

from app.core.config import settings
from app.core.errors import AppError, bad_request, forbidden, not_found
from app.models.models import Attachment, Event
from app.repositories import AttachmentRepo, RegistrationRepo, SessionRepo, SpeakerRepo
from app.services.audit import audit
from app.services.permissions import RANK, get_event_visible, require_role

ENTITY_TYPES = ("event", "session", "speaker", "registration")


def _is_text(b: bytes) -> bool:
    if b"\x00" in b:
        return False
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _zip_has(b: bytes, member: str) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            return member in z.namelist()
    except zipfile.BadZipFile:
        return False


# mime -> (allowed extensions, content check). Content is verified from the bytes; the client's claims are never trusted.
ALLOWED = {
    "application/pdf": ({".pdf"}, lambda b: b.startswith(b"%PDF-")),
    "image/png": ({".png"}, lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/jpeg": ({".jpg", ".jpeg"}, lambda b: b.startswith(b"\xff\xd8\xff")),
    "image/gif": ({".gif"}, lambda b: b[:6] in (b"GIF87a", b"GIF89a")),
    "text/plain": ({".txt", ".md"}, _is_text),
    "text/csv": ({".csv"}, _is_text),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ({".docx"}, lambda b: _zip_has(b, "word/document.xml")),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ({".xlsx"}, lambda b: _zip_has(b, "xl/workbook.xml")),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ({".pptx"}, lambda b: _zip_has(b, "ppt/presentation.xml")),
}
EXT_TO_MIME = {ext: mime for mime, (exts, _) in ALLOWED.items() for ext in exts}


def validate(filename: str, declared_mime: str, content: bytes) -> tuple[str, str]:
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    ext = os.path.splitext(name)[1].lower()
    if not name or ext not in EXT_TO_MIME:
        raise AppError(415, "INVALID_FILE_EXTENSION", f"File extension '{ext}' is not allowed.")
    if (declared_mime or "").split(";")[0].strip().lower() not in ALLOWED:
        raise AppError(415, "INVALID_MIME_TYPE", f"MIME type '{declared_mime}' is not allowed.")
    mime = EXT_TO_MIME[ext]
    if declared_mime.split(";")[0].strip().lower() != mime:
        raise AppError(415, "INVALID_MIME_TYPE", "The declared MIME type does not match the file extension.")
    if not content:
        raise bad_request("EMPTY_FILE", "The uploaded file is empty.")
    if not ALLOWED[mime][1](content):
        raise bad_request("FILE_CONTENT_MISMATCH", "The file contents do not match its type.")
    return name[:255], mime


async def read_limited(upload) -> bytes:
    data = bytearray()
    while chunk := await upload.read(64 * 1024):
        data += chunk
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise AppError(413, "FILE_TOO_LARGE", f"Files may be at most {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return bytes(data)


def _check_entity(db, ev: Event, entity_type: str, entity_id: int, user, role: str):
    if entity_type not in ENTITY_TYPES:
        raise bad_request("INVALID_ENTITY_TYPE", f"entity_type must be one of {', '.join(ENTITY_TYPES)}.")
    if entity_type == "event":
        ok = entity_id == ev.id
    elif entity_type == "session":
        s = SessionRepo(db).get(entity_id)
        ok = bool(s and s.event_id == ev.id)
    elif entity_type == "speaker":
        s = SpeakerRepo(db).get(entity_id)
        ok = bool(s and s.organization_id == ev.organization_id)
    else:
        r = RegistrationRepo(db).get(entity_id)
        ok = bool(r and r.event_id == ev.id)
        if ok and RANK[role] < RANK["staff"] and r.user_id != user.id:
            raise forbidden("FORBIDDEN", "You can only attach files to your own registration.")
    if not ok:
        raise not_found(entity_type.capitalize())


def save(db, user, event_id, entity_type, entity_id, filename, declared_mime, content: bytes) -> Attachment:
    ev, role = get_event_visible(db, user, event_id)
    if entity_type != "registration" and RANK[role] < RANK["staff"]:
        raise forbidden("INSUFFICIENT_PERMISSIONS", "Only staff can upload files to this resource.")
    _check_entity(db, ev, entity_type, entity_id, user, role)
    name, mime = validate(filename, declared_mime, content)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{os.path.splitext(name)[1].lower()}"
    path = os.path.join(settings.UPLOAD_DIR, stored)
    with open(path, "wb") as fh:
        fh.write(content)
    att = AttachmentRepo(db).add(Attachment(event_id=ev.id, entity_type=entity_type, entity_id=entity_id, file_name=name, mime_type=mime,
                                            file_size=len(content), storage_path=path, uploaded_by=user.id))
    audit(db, user, "file.upload", "attachment", att.id, ev.organization_id, {"name": name})
    db.commit()
    return att


def _visible(db, user, att, role) -> bool:
    if RANK[role] >= RANK["staff"]:
        return True
    if att.entity_type in ("event", "session"):
        return True
    if att.entity_type == "registration":
        r = RegistrationRepo(db).get(att.entity_id)
        return bool(r and r.user_id == user.id)
    return False


def list_for_event(db, user, event_id, entity_type=None, entity_id=None):
    ev, role = get_event_visible(db, user, event_id)
    return [a for a in AttachmentRepo(db).for_event(ev.id, entity_type, entity_id) if _visible(db, user, a, role)]


def get_for_download(db, user, att_id) -> Attachment:
    att = AttachmentRepo(db).get(att_id)
    if not att:
        raise not_found("File")
    ev, role = get_event_visible(db, user, att.event_id)
    if not _visible(db, user, att, role):
        raise forbidden("FORBIDDEN", "You do not have access to this file.")
    if not os.path.exists(att.storage_path):
        raise not_found("File")
    return att


def delete(db, user, att_id):
    att = AttachmentRepo(db).get(att_id)
    if not att:
        raise not_found("File")
    ev, role = get_event_visible(db, user, att.event_id, "staff")
    if att.uploaded_by != user.id and RANK[role] < RANK["event_manager"]:
        raise forbidden("INSUFFICIENT_PERMISSIONS", "Only the uploader or a manager can delete this file.")
    path = att.storage_path
    audit(db, user, "file.delete", "attachment", att.id, ev.organization_id)
    AttachmentRepo(db).delete(att)
    db.commit()
    try:
        os.remove(path)
    except OSError:
        pass
