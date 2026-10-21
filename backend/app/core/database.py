import threading
import zlib
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # enforce FKs / cascades in SQLite (used by tests)
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Always store UTC and always return tz-aware datetimes (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_local_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


@contextmanager
def locked(db, key: str):
    """Serialise a critical section (capacity / overlap checks).

    PostgreSQL: transaction-scoped advisory lock, released on commit/rollback.
    Other dialects (SQLite in tests): process-local mutex held until the block exits,
    so callers must commit *inside* the block.
    """
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": zlib.crc32(key.encode())})
        yield
    else:
        with _local_locks[key]:
            yield
