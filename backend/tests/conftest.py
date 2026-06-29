import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.user import User
from app.repositories.deps import get_user_repository
from app.repositories.user import UserRepository


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        async with session_factory() as test_session:
            yield test_session
            await test_session.close()
        await transaction.rollback()

    await engine.dispose()


@pytest.fixture
def user_repo(session: AsyncSession) -> UserRepository:
    return get_user_repository(session)


def make_user(suffix: str | None = None) -> User:
    unique = suffix or uuid.uuid4().hex[:8]
    return User(
        email=f"user-{unique}@example.com",
        password_hash="hashed-password",
        full_name=f"Test User {unique}",
        telegram_id=int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000,
    )
