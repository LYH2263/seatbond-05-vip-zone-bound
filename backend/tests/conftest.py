import os
import tempfile

# Point the app at a throwaway SQLite file before any app module is imported,
# so lifespan create_all/seed never touches the real Postgres.
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="seatbond-test-", suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SEED_ON_EMPTY"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import ConflictLog, Hall, SeatHold, Showtime, VipZone  # noqa: E402


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c
