import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_current_user
from app.api import auth, content, events, organizations, registrations, resources
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError, register_handlers
from app.core.security import decode_token
from app.repositories import UserRepo
from app.services import auth as auth_svc, jobs
from app.services.realtime import manager

log = logging.getLogger("eventhub")


async def _scheduler():
    loop = asyncio.get_running_loop()
    while True:
        await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
        await loop.run_in_executor(None, jobs.run_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.loop = asyncio.get_running_loop()
    db = SessionLocal()
    try:
        auth_svc.seed_roles(db)  # no-op when migrations already seeded them
        auth_svc.seed_super_admin(db)
    except Exception:
        log.exception("startup seeding failed (have migrations been applied?)")
    finally:
        db.close()
    task = asyncio.create_task(_scheduler()) if settings.ENABLE_SCHEDULER else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="EventHub API", version="1.0.0", lifespan=lifespan,
              description="Collaborative event & resource booking platform.")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
register_handlers(app)
for r in (auth.router, organizations.router, events.router, registrations.router, resources.router, content.router):
    app.include_router(r)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.post("/api/admin/run-jobs", tags=["meta"])
def run_jobs_now(user=Depends(get_current_user)):
    """Super-admin helper: run the periodic jobs (reminders, status changes, booking completion) immediately."""
    if not user.is_super_admin:
        raise AppError(403, "INSUFFICIENT_PERMISSIONS", "Super admin only.")
    return jobs.run_all()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str):
    """Authenticate with ?token=<access token>. Server pushes {event, data} JSON messages."""
    try:
        payload = decode_token(token, "access")
        db = SessionLocal()
        try:
            user = UserRepo(db).get(int(payload["sub"]))
            ok = bool(user and user.is_active)
        finally:
            db.close()
    except AppError:
        ok = False
    if not ok:
        await ws.close(code=4401)
        return
    uid = int(payload["sub"])
    await manager.connect(uid, ws)
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(uid, ws)
