import os
import tempfile

# Configure BEFORE importing the app: tests run on a throw-away SQLite file (the app code is dialect-agnostic;
# PostgreSQL-only extras such as exclusion constraints live in the Alembic migration).
_tmp = tempfile.mkdtemp(prefix="eventhub-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["ENABLE_SCHEDULER"] = "0"
os.environ["SECRET_KEY"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth import seed_roles  # noqa: E402
from tests.helpers import World  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_roles(db)
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def w(client):
    """Two tenants: org A (admin, manager, staff, 3 participants) and org B (its own admin)."""
    return World(client)
