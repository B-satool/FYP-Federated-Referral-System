from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_session_factory(url: str):
    engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return engine, sessionmaker(engine, expire_on_commit=False)


def session_dependency(factory):
    def get_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    return get_db
