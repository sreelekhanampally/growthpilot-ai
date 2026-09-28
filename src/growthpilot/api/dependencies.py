from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine

from growthpilot.db.session import build_engine, resolve_database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return build_engine(resolve_database_url(None))
