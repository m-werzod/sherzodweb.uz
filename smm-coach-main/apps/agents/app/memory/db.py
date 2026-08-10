"""Shared async SQLAlchemy engine for the agents service.

Note: LangGraph's PostgresSaver uses its own psycopg pool, separate from this
engine. We use SQLAlchemy here for the typed memory queries
(agent_memory + shared_knowledge).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        # SQLAlchemy expects `postgresql+asyncpg://` — translate from the
        # plain `postgresql://` form used by Prisma.
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        # asyncpg does not accept query params like `schema=`. Strip them.
        if "?" in url:
            url = url.split("?")[0]
        _engine = create_async_engine(url, pool_pre_ping=True, pool_size=5)
    return _engine


def get_sessionmaker() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
