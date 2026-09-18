from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_schema() -> None:
    """项目无迁移工具：补齐老库缺失的列（create_all 只建新表）。"""
    inspector = inspect(engine)
    if "seat_holds" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("seat_holds")}
        if "vip_request" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE seat_holds ADD COLUMN vip_request BOOLEAN DEFAULT FALSE"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="SeatBond", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
