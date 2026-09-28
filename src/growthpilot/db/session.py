import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def resolve_database_url(explicit_url: str | None = None) -> str:
    url = explicit_url or os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is required; see .env.example")
    parsed = make_url(url)
    if parsed.drivername not in {
        "postgresql",
        "postgresql+psycopg",
        "sqlite",
        "sqlite+pysqlite",
    }:
        raise ValueError(f"Unsupported database driver: {parsed.drivername}")
    # Render and several other managed providers expose ``postgresql://`` URLs.
    # This project installs psycopg 3 (not psycopg2), so make the driver explicit.
    if parsed.drivername == "postgresql":
        return parsed.set(drivername="postgresql+psycopg").render_as_string(
            hide_password=False
        )
    return url


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    engine = create_engine(database_url, echo=echo, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    session = session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
