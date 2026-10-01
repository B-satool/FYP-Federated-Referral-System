from refcommon.db import make_session_factory, session_dependency
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


engine, SessionLocal = make_session_factory(settings.database_url)
get_db = session_dependency(SessionLocal)
