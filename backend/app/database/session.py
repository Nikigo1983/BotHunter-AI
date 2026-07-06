import contextvars
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

connect_args: dict[str, object] = {"command_timeout": 30}
if settings.requires_postgres_ssl:
    connect_args["ssl"] = True
if settings.database_use_pooler:
    connect_args["prepared_statement_cache_size"] = 0

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_recycle=settings.database_pool_recycle,
    connect_args=connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

_request_db_session: contextvars.ContextVar[AsyncSession | None] = contextvars.ContextVar(
    "_request_db_session",
    default=None,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    existing = _request_db_session.get()
    if existing is not None:
        yield existing
        return

    async with async_session_factory() as session:
        token = _request_db_session.set(session)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            _request_db_session.reset(token)


def reset_request_db_session() -> None:
    _request_db_session.set(None)
