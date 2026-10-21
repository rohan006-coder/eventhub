import io
import zipfile

from app.core.config import settings
from tests.helpers import err

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.4\n%fake\n"


def up(actor, ev, name, data, mime, **form):
    return actor.post(f"/api/events/{ev['id']}/attachments", files={"file": (name, data, mime)}, data={"entity_type": "event", **form})


def test_valid_upload_download_and_list(w):
    ev = w.event(publish=True)
    r = up(w.manager, ev, "../../poster.png", PNG, "image/png")
    assert r.status_code == 201
    f = r.json()
    assert f["file_name"] == "poster.png" and f["mime_type"] == "image/png" and f["file_size"] == len(PNG)  # path stripped
    assert len(w.p1.get(f"/api/events/{ev['id']}/attachments").json()) == 1
    d = w.p1.get(f"/api/attachments/{f['id']}/download")
    assert d.status_code == 200 and d.content == PNG and d.headers["x-content-type-options"] == "nosniff"
    assert w.outsider.get(f"/api/attachments/{f['id']}/download").status_code == 403


def test_valid_docx(w):
    ev = w.event(publish=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<x/>")
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert up(w.manager, ev, "a.docx", buf.getvalue(), mime).status_code == 201


def test_invalid_mime_type(w):
    ev = w.event(publish=True)
    r = up(w.manager, ev, "a.png", PNG, "text/html")
    assert r.status_code == 415 and err(r) == "INVALID_MIME_TYPE"
    r = up(w.manager, ev, "a.png", PNG, "application/pdf")   # allowed type but wrong for the extension
    assert err(r) == "INVALID_MIME_TYPE"


def test_invalid_extension(w):
    ev = w.event(publish=True)
    r = up(w.manager, ev, "evil.exe", b"MZ", "image/png")
    assert r.status_code == 415 and err(r) == "INVALID_FILE_EXTENSION"
    assert err(up(w.manager, ev, "noext", PNG, "image/png")) == "INVALID_FILE_EXTENSION"
    assert err(up(w.manager, ev, "x.svg", b"<svg/>", "image/svg+xml")) == "INVALID_FILE_EXTENSION"


def test_content_is_verified_not_trusted(w):
    ev = w.event(publish=True)
    r = up(w.manager, ev, "fake.png", b"<script>alert(1)</script>", "image/png")
    assert r.status_code == 400 and err(r) == "FILE_CONTENT_MISMATCH"
    assert err(up(w.manager, ev, "fake.pdf", PNG, "application/pdf")) == "FILE_CONTENT_MISMATCH"
    assert err(up(w.manager, ev, "fake.docx", b"PK\x03\x04junk", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")) == "FILE_CONTENT_MISMATCH"
    assert err(up(w.manager, ev, "empty.txt", b"", "text/plain")) == "EMPTY_FILE"


def test_oversized_file(w, monkeypatch):
    ev = w.event(publish=True)
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 64)
    r = up(w.manager, ev, "big.pdf", PDF + b"x" * 100, "application/pdf")
    assert r.status_code == 413 and err(r) == "FILE_TOO_LARGE"


def test_upload_authorization(w):
    ev = w.event(publish=True)
    assert up(w.p1, ev, "a.png", PNG, "image/png").status_code == 403          # participants can't attach to the event
    assert up(w.outsider, ev, "a.png", PNG, "image/png").status_code == 403    # other tenant
    # participants may attach to their own registration only
    reg = w.p1.post(f"/api/events/{ev['id']}/register").json()
    mine = w.p1.post(f"/api/events/{ev['id']}/attachments", files={"file": ("id.pdf", PDF, "application/pdf")},
                     data={"entity_type": "registration", "entity_id": str(reg["id"])})
    assert mine.status_code == 201
    other = w.p2.post(f"/api/events/{ev['id']}/attachments", files={"file": ("id.pdf", PDF, "application/pdf")},
                      data={"entity_type": "registration", "entity_id": str(reg["id"])})
    assert other.status_code == 403
    assert w.p2.get(f"/api/attachments/{mine.json()['id']}/download").status_code == 403
    assert w.staff.get(f"/api/attachments/{mine.json()['id']}/download").status_code == 200


def test_entity_must_belong_to_event(w):
    ev = w.event(publish=True)
    r = w.manager.post(f"/api/events/{ev['id']}/attachments", files={"file": ("a.png", PNG, "image/png")},
                       data={"entity_type": "session", "entity_id": "9999"})
    assert r.status_code == 404
