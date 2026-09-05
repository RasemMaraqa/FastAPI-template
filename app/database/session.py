from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """All models inherit this base so Alembic can discover their tables."""


url = get_settings().database_url
engine = create_engine(
    url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
)
if url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """Use Depends(get_db). Commit explicitly in writes; exceptions roll back on close."""
    with SessionLocal() as session:
        yield session
