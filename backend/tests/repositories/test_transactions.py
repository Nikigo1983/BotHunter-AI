import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.repositories.deps import get_user_repository
from tests.conftest import make_user


@pytest.mark.asyncio
async def test_transaction_rollback_discards_created_user() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    user = make_user("transaction")

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            repo = get_user_repository(session)
            created = await repo.create(user)
            created_id = created.id

        await transaction.rollback()

    async with engine.connect() as connection:
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            repo = get_user_repository(session)
            assert await repo.get_by_id(created_id) is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_transaction_commit_persists_created_user() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    user = make_user("commit")
    created_id = None

    async with engine.connect() as connection:
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            repo = get_user_repository(session)
            created = await repo.create(user)
            created_id = created.id
            await session.commit()

    async with engine.connect() as connection:
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            repo = get_user_repository(session)
            fetched = await repo.get_by_id(created_id)
            assert fetched is not None
            assert fetched.email == user.email
            await repo.delete(fetched)
            await session.commit()

    await engine.dispose()
