import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.admin.auth.passwords import hash_password
from app.config import get_settings
from app.models.dashboard_user import DashboardUser
from app.models.enums import DashboardRole
from app.models.user import User
from app.repositories.deps import get_dashboard_user_repository, get_user_repository
from app.repositories.user import UserRepository
from app.services.dashboard_auth import DashboardAuthService, SESSION_COOKIE_NAME
from app.main import app


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


@pytest_asyncio.fixture
async def dashboard_owner(session: AsyncSession) -> DashboardUser:
    repo = get_dashboard_user_repository(session)
    existing = await repo.get_by_email("admin@test.local")
    if existing is not None:
        return existing
    return await repo.create(
        DashboardUser(
            email="admin@test.local",
            password_hash=hash_password("testpass"),
            full_name="Test Admin",
            role=DashboardRole.OWNER.value,
            is_active=True,
        )
    )


@pytest_asyncio.fixture
async def admin_client(session: AsyncSession, dashboard_owner: DashboardUser) -> AsyncClient:
    from app.database.session import get_db_session

    async def override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    auth_service = DashboardAuthService(session)
    token, _ = await auth_service.create_session(dashboard_owner)
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, token)
    yield client
    await client.aclose()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_csrf(admin_client: AsyncClient, session: AsyncSession, dashboard_owner: DashboardUser) -> str:
    token = admin_client.cookies.get(SESSION_COOKIE_NAME)
    auth = await DashboardAuthService(session).resolve_session(token)
    assert auth is not None
    return auth.csrf_token
